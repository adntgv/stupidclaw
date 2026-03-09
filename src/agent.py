import json
import re
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
import requests as http_requests
from openai import OpenAI
from src.config import OPENAI_API_KEY, OPENAI_BASE_URL, MODEL_NAME
from src.tools import get_default_tools
from src.memory import MemoryManager
from src.subagents import SubAgentManager, SelfModifier
from src.self_heal import SelfHealer

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=3)


class StupidAgent:
    def __init__(self, data_dir: str = "/app/data"):
        self.client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        self.api_base = OPENAI_BASE_URL.rstrip('/')
        self.api_key = OPENAI_API_KEY
        self.model = MODEL_NAME
        self.tools = get_default_tools()
        self.memory = MemoryManager(data_dir=data_dir)
        self.subagent_manager = SubAgentManager(self)
        self.self_modifier = SelfModifier(self.memory)
        self.self_healer = SelfHealer(data_dir=data_dir)

    def _tools_to_openai_schema(self) -> list:
        """Convert internal tools to OpenAI function calling format"""
        schemas = []
        for tool_name, tool in self.tools.items():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "args": {
                                "type": "string",
                                "description": tool.args_description
                            }
                        },
                        "required": ["args"]
                    }
                }
            })
        return schemas

    def run(self, user_message: str, chat_id: str = "default") -> str:
        """
        Simplified: let LLM use native function calling
        """
        # Log user message
        self.memory.add_user_message(chat_id, user_message)
        
        # IMMEDIATE fact storage: store "remember X" facts BEFORE routing
        msg_lower = user_message.lower()
        if any(kw in msg_lower for kw in ["remember", "my name is", "i live in", "i am"]):
            self.memory.store_fact(chat_id, user_message, {"type": "user_info"})
            logger.info(f"Stored fact immediately: {user_message[:60]}")
        
        # Build memory context for this query
        memory_context = self.memory.build_context(chat_id, user_message, budget=3000)
        
        try:
            # Build system prompt with memory
            system_prompt = "You are StupidClaw, an AI assistant. You have access to tools. Use them when needed to answer questions accurately."
            if memory_context:
                system_prompt += f"\n\nContext from memory:\n{memory_context[:1000]}"
            
            # Get conversation history (last 10 messages, excluding current which was just added)
            conversation_history = self.memory.hot.get_history(chat_id, max_messages=11)
            
            # Build messages: system + history (excluding the just-added current message)
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history except the last message (which is the current user message we just logged)
            if len(conversation_history) > 1:
                messages.extend(conversation_history[:-1])
            
            # Add current user message
            messages.append({"role": "user", "content": user_message})
            
            # Call LLM with tools
            answer = self._llm_with_tools(messages, chat_id)
            
            # Safety check: ensure we always have a string response
            if answer is None or not isinstance(answer, str):
                answer = "I processed your request but couldn't generate a response."
            
            # Self-healing: Check for errors in response
            if self.self_healer.check_for_errors(answer):
                logger.warning("Error detected in response, logging for analysis")
                self.self_healer.log_error(chat_id, "Error in response", user_message)
            
            # Periodic error pattern review
            self.self_healer.periodic_review()
            
            # Log bot response
            self.memory.add_bot_response(chat_id, answer)
            
            # Self-modification: extract and store facts
            self.self_modifier.extract_and_store_facts(user_message, answer, chat_id)
            
            return answer
            
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            logger.error(error_msg)
            self.memory.log_error(chat_id, error_msg, user_message)
            self.self_healer.log_error(chat_id, error_msg, user_message)
            return f"Sorry, I encountered an error: {str(e)}"

    def _llm_with_tools(self, messages: list, chat_id: str = "default", max_iterations: int = 5) -> str:
        """
        Call LLM with native function calling support.
        Handles tool call loop automatically.
        """
        tools_schema = self._tools_to_openai_schema()
        conversation = messages.copy()
        
        for iteration in range(max_iterations):
            try:
                # Call LLM with tools
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=conversation,
                    tools=tools_schema,
                    tool_choice="auto",
                    max_tokens=1024
                )
                
                message = response.choices[0].message
                
                # If no tool calls, return the text response
                if not message.tool_calls:
                    text = message.content or ""
                    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
                
                # Add assistant message to conversation
                # Note: message.content can be None when there are only tool calls
                assistant_msg = {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in message.tool_calls
                    ]
                }
                # Only add content if it's not None
                if message.content:
                    assistant_msg["content"] = message.content
                
                conversation.append(assistant_msg)
                
                # Execute each tool call
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                        args_str = function_args.get("args", "")
                    except:
                        args_str = tool_call.function.arguments
                    
                    logger.info(f"Calling tool: {function_name}({args_str})")
                    
                    # Execute the tool
                    result = self._execute_tool(function_name, args_str, chat_id)
                    
                    # Add tool result to conversation
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result[:2000]  # Truncate long results
                    })
                
                # Continue loop to get final answer with tool results
                
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                # Fallback to simple response
                return self._llm(messages)
        
        # If we hit max iterations, return last response
        return "I've used several tools but couldn't formulate a final answer. Please try rephrasing your question."

    def _execute_tool(self, tool_name: str, args, chat_id: str = "default") -> str:
        """Execute a tool and return string result"""
        # Check if tool is disabled by self-healer
        if self.self_healer.is_tool_disabled(tool_name):
            logger.warning(f"Tool '{tool_name}' is disabled, trying alternative")
            alt_tool = self.self_healer.get_alternative_tool(tool_name, self.tools)
            if alt_tool:
                logger.info(f"Using alternative tool '{alt_tool}' instead of '{tool_name}'")
                tool_name = alt_tool
            else:
                return f"Tool '{tool_name}' is currently disabled and no alternative available"
        
        tool = self.tools.get(tool_name)
        if not tool:
            # Self-heal: suggest correct tool
            available = list(self.tools.keys())
            logger.warning(f"Unknown tool '{tool_name}', available: {available}")
            return f"Tool '{tool_name}' not found. Available tools: {', '.join(available)}. Please use one of these."
        
        # Convert args to string format expected by tools
        args_str = str(args) if not isinstance(args, str) else args
        
        result = tool.execute(args_str)
        
        # Self-healing: Check if tool execution failed
        if not result.success:
            logger.warning(f"Tool '{tool_name}' failed: {result.output[:100]}")
            self.self_healer.log_error(chat_id, result.output, f"Tool: {tool_name}, Args: {args_str}", tool_name)
            
            # Mark tool for potential disabling if failing repeatedly
            self.self_healer.should_disable_tool(tool_name, threshold=5)
        
        # Log tool usage to memory
        self.memory.log_tool_use(chat_id, tool_name, args_str, result.output)
        
        return result.output

    def _llm(self, messages: list) -> str:
        """Simple LLM call without tools (fallback)"""
        try:
            c = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1024
            )
            text = c.choices[0].message.content or ""
            # Strip <think> blocks (Qwen, DeepSeek)
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
            return text
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return f"Error calling LLM: {str(e)}"
