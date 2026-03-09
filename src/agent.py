import json
import re
import logging
from openai import OpenAI
from src.config import OPENAI_API_KEY, OPENAI_BASE_URL, MODEL_NAME
from src.tools import get_default_tools
from src.memory import MemoryManager

logger = logging.getLogger(__name__)


class StupidAgent:
    def __init__(self, data_dir: str = "/app/data"):
        self.client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        self.model = MODEL_NAME
        self.tools = get_default_tools()
        self.memory = MemoryManager(data_dir=data_dir)

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

    def _build_system_prompt(self, memory_context: str = "") -> str:
        """Build a system prompt optimized for weaker models (explicit, step-by-step)"""
        tools_list = "\n".join(f"- {name}: {tool.description}" for name, tool in self.tools.items())
        
        prompt = f"""You are StupidClaw. You have tools and memory.

TOOLS:
{tools_list}

RULES:
1. Use tools when you need information
2. If a tool says ERROR, try a different tool or approach
3. Always explain what you're doing

EXAMPLES:

User asks about weather:
1. Call web_search with "weather [city]"
2. If it fails, call web_fetch with a weather URL
3. Tell the user what you found

User says "retry":
1. Look at previous messages (you have memory)
2. See what failed
3. Try a different way
4. Explain: "Last time I tried X and got error Y. Now trying Z instead."

ERROR handling:
- Tool returns "ERROR: ..." → try different tool
- Tool returns "TOOL ERROR: ..." → try different approach
- If stuck after 2 tries → tell user what went wrong and ask for help"""

        if memory_context:
            prompt += f"\n\nRECENT MEMORY:\n{memory_context[:600]}"
        
        return prompt

    def run(self, user_message: str, chat_id: str = "default") -> str:
        """Main agent loop with LLM reasoning and error feedback"""
        # Store user message
        self.memory.add_user_message(chat_id, user_message)
        
        # Build memory context
        memory_context = self.memory.build_context(chat_id, user_message, budget=3000)
        
        # Get conversation history
        conversation_history = self.memory.hot.get_history(chat_id, max_messages=11)
        
        # Build messages with strong system prompt
        messages = [
            {"role": "system", "content": self._build_system_prompt(memory_context)}
        ]
        
        # Add conversation history (filter out invalid messages)
        if len(conversation_history) > 1:
            for msg in conversation_history[:-1]:
                if msg.get("content"):  # Only add messages with content
                    messages.append(msg)
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        try:
            # Run LLM with tools and error feedback
            answer = self._run_with_tools(messages, chat_id)
            
            # Store response
            if answer:
                self.memory.add_bot_response(chat_id, answer)
            
            return answer or "I couldn't process that request."
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.memory.log_error(chat_id, error_msg, user_message)
            return f"I encountered an error: {str(e)}"

    def _run_with_tools(self, messages: list, chat_id: str, max_rounds: int = 3) -> str:
        """
        Run LLM with tools, letting it see errors and reason about them.
        No defensive checks - let the LLM handle everything.
        """
        tools_schema = self._tools_to_openai_schema()
        conversation = messages.copy()
        
        for round_num in range(max_rounds):
            try:
                # Call LLM with tools
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=conversation,
                    tools=tools_schema,
                    tool_choice="auto",
                    max_tokens=1024  # Enough for weak models
                )
                
                message = response.choices[0].message
                
                # If no tool calls, we have a final answer
                if not message.tool_calls:
                    text = message.content or ""
                    # Clean up thinking tags
                    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
                    
                    # Weak models sometimes give empty responses - prompt them again
                    if not text and round_num < max_rounds - 1:
                        conversation.append({
                            "role": "system",
                            "content": "Please provide an answer. What did you find from the tools?"
                        })
                        continue
                    
                    return text if text else None
                
                # LLM wants to use tools - add its message to conversation
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
                
                # Add content if present
                if message.content:
                    assistant_msg["content"] = message.content
                
                conversation.append(assistant_msg)
                
                # Execute each tool call
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    
                    # Parse arguments
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                        args_str = function_args.get("args", "")
                    except:
                        args_str = tool_call.function.arguments
                    
                    logger.info(f"[Round {round_num+1}] Calling {function_name}({args_str[:50]}...)")
                    
                    # Execute tool (no error handling - let it fail naturally)
                    result = self._execute_tool(function_name, args_str, chat_id)
                    
                    # Add result to conversation (LLM will see success or error)
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result[:1200]  # Keep it focused for weak models
                    })
                
                # Continue loop - LLM will see tool results and decide next step
                
            except Exception as e:
                # Even API errors go back to the LLM as context
                logger.error(f"LLM call failed: {e}")
                conversation.append({
                    "role": "system",
                    "content": f"API Error: {str(e)}\n\nPlease explain what happened and what we should try next."
                })
                # One more round to let LLM respond to the error
                continue
        
        # If we hit max rounds, give explicit instructions
        conversation.append({
            "role": "system",
            "content": "You've tried 3 times. Now give your final answer: What did you learn? If you couldn't complete the task, say exactly what went wrong and what the user should do."
        })
        
        try:
            final_response = self.client.chat.completions.create(
                model=self.model,
                messages=conversation,
                max_tokens=1024
            )
            text = final_response.choices[0].message.content or ""
            return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        except:
            return None

    def _execute_tool(self, tool_name: str, args: str, chat_id: str) -> str:
        """
        Execute a tool and return the result (success or error).
        NO error handling - let failures propagate naturally as tool results.
        """
        tool = self.tools.get(tool_name)
        
        # Tool not found - return error message (LLM will see this)
        if not tool:
            available = ", ".join(self.tools.keys())
            return f"ERROR: Tool '{tool_name}' not found. Available tools: {available}"
        
        # Execute tool
        try:
            result = tool.execute(str(args))
            
            # Log to memory
            self.memory.log_tool_use(chat_id, tool_name, str(args), result.output)
            
            # Return result (success or failure - LLM decides what to do)
            if result.success:
                return result.output
            else:
                return f"TOOL ERROR: {result.output}"
                
        except Exception as e:
            # Tool crashed - return exception (LLM will see and reason about it)
            return f"TOOL EXCEPTION: {str(e)}"
