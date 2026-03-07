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

    def run(self, user_message: str, chat_id: str = "default") -> str:
        """
        Cascade architecture:
        1. ROUTE: classify easy | medium | hard
        2. EASY: direct answer (one pass)
        3. MEDIUM: plan → tools → answer with evidence
        4. HARD: 3 parallel clones → judge → final answer
        5. VERIFY: always
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
        
        # Step 1: Route FIRST (before planning)
        # Force medium for "run:" commands (need tools)
        if msg_lower.startswith("run:") or msg_lower.startswith("run "):
            difficulty = "medium"
        # Force easy if hot memory has relevant facts (no need to web search)
        elif self.memory.hot.recall_facts(chat_id) and any(kw in msg_lower for kw in ["what is my", "what's my", "do you know", "recall", "remember"]):
            difficulty = "easy"
        else:
            difficulty = self._route(user_message, memory_context)
        logger.info(f"Route: {difficulty} | Message: {user_message[:80]}")

        try:
            # Self-healing loop: retry up to 2 times on verification failure
            for attempt in range(2):
                if difficulty == "easy":
                    answer = self._easy_lane(user_message, memory_context)
                elif difficulty == "hard":
                    answer = self._hard_lane(user_message, memory_context)
                else:  # medium (default)
                    answer = self._medium_lane(user_message, memory_context, chat_id)

                # Verify (skip for easy lane - no need to verify greetings)
                if difficulty == "easy":
                    verified = True
                else:
                    verified = self._verify(user_message, answer)
                if verified:
                    break
                
                # Self-heal: escalate difficulty and retry
                if attempt == 0:
                    logger.warning(f"Verification failed (attempt {attempt+1}), escalating difficulty")
                    if difficulty == "easy":
                        difficulty = "medium"
                    elif difficulty == "medium":
                        difficulty = "hard"
                    # Log the failure for learning
                    self.memory.log_error(chat_id, f"Verification failed on {difficulty} lane, escalating", user_message)
                    continue
            
            if not verified:
                answer = answer + "\n\n(Note: I'm not fully confident in this answer.)"
            
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

    # ── ROUTER ──────────────────────────────────────────

    def _route(self, message: str, memory_context: str = "") -> str:
        """Tiny classifier: easy | medium | hard"""
        resp = self._llm([
            {"role": "system", "content": (
                "Classify this message as exactly one word: easy, medium, or hard.\n"
                "easy = greeting, simple fact, chitchat, simple math, recall from memory\n"
                "medium = needs web search, file lookup, multi-step calculation\n"
                "hard = ambiguous, complex reasoning, multiple sources needed, controversial\n"
                "Reply with ONLY one word."
            )},
            {"role": "user", "content": message}
        ])
        word = resp.strip().lower().split()[0] if resp else "medium"
        if word in ("easy", "medium", "hard"):
            return word
        return "medium"

    # ── EASY LANE ───────────────────────────────────────

    def _easy_lane(self, message: str, memory_context: str = "") -> str:
        """One pass. Direct answer. No tools."""
        tool_names = list(self.tools.keys())
        system_prompt = (
            f"You are StupidClaw, an AI assistant. You have these tools: {', '.join(tool_names)}. "
            "Answer directly and briefly."
        )
        if memory_context:
            system_prompt += f"\n\nContext:\n{memory_context[:1000]}"
        
        return self._llm([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ])

    # ── MEDIUM LANE ─────────────────────────────────────

    def _medium_lane(self, message: str, memory_context: str = "", chat_id: str = "default") -> str:
        """Plan → execute tools → answer with evidence + sufficiency check."""
        # Determine mode/aperture based on message content
        mode = self._classify_mode(message)
        logger.info(f"Operating in {mode.upper()} mode")
        
        # Plan
        plan = self._plan(message, mode)
        logger.info(f"Plan: {json.dumps(plan)}")

        # Execute tools with evidence sufficiency loop (max 2 rounds)
        all_evidence = []
        for retrieval_round in range(2):
            round_results = []
            
            # Execute current plan steps
            for step in plan.get("steps", []):
                tool = step.get("tool", "none")
                if tool == "none":
                    continue
                result = self._execute_tool(tool, step.get("args", ""), chat_id)
                round_results.append(f"{step.get('description', tool)}: {result}")
            
            all_evidence.extend(round_results)
            
            # Check evidence sufficiency (skip on first round if results look good >100 chars)
            if round_results:
                # Quick heuristic: if we got substantial results (>100 chars), skip LLM check
                total_chars = sum(len(r) for r in round_results)
                if total_chars > 100 and retrieval_round == 0:
                    logger.info(f"Sufficient evidence ({total_chars} chars), skipping verification")
                    break
                
                sufficient = self._check_evidence_sufficiency(message, all_evidence)
                if sufficient or retrieval_round >= 1:
                    break
                else:
                    logger.info("Evidence insufficient, retrieving more...")
                    # Get another plan with context of what we already have
                    plan = self._plan(
                        f"Original question: {message}\nWe already have: {', '.join([r[:50] for r in all_evidence])}\nWhat else do we need?",
                        mode
                    )

        # Answer with evidence
        if all_evidence:
            context = f"User asked: {message}\n"
            if memory_context:
                context += f"Memory:\n{memory_context[:500]}\n\n"
            context += "Evidence:\n" + "\n".join(f"- {r}" for r in all_evidence)
            
            tool_names = list(self.tools.keys())
            return self._llm([
                {"role": "system", "content": (
                    f"You are StupidClaw, an AI assistant with tools: {', '.join(tool_names)}. "
                    f"{self._get_mode_prompt(mode)}\n"
                    "The evidence below was gathered by YOUR tools (web_search, web_fetch, etc). "
                    "Answer based on this evidence. Be brief and direct."
                )},
                {"role": "user", "content": context}
            ])
        else:
            return self._easy_lane(message, memory_context)

    # ── HARD LANE ───────────────────────────────────────

    def _hard_lane(self, message: str, memory_context: str = "") -> str:
        """
        Improved committee-of-clones: 3 parallel clones with DIFFERENT evidence
        Each gets different retrieved context, then deterministic scoring
        """
        mode = self._classify_mode(message)
        
        # Get 3 different evidence sets (varied search/retrieval)
        evidence_sets = self._get_diverse_evidence(message, mode, num_sets=3)
        
        context_snippet = f"\n\nContext:\n{memory_context[:500]}" if memory_context else ""
        
        # 3 clones, each with different evidence
        candidates = []
        for i, evidence in enumerate(evidence_sets):
            evidence_text = "\n- ".join(evidence) if evidence else "No additional evidence"
            prompt = (
                f"{self._get_mode_prompt(mode)}\n"
                f"{context_snippet}\n"
                f"Evidence set {i+1}:\n{evidence_text}\n\n"
                f"Answer based on this evidence. Be thorough but clear."
            )
            
            resp = self._llm([
                {"role": "system", "content": prompt},
                {"role": "user", "content": message}
            ])
            candidates.append({
                "answer": resp,
                "evidence": evidence
            })

        # Deterministic scorer based on evidence coverage
        best_idx = self._score_candidates(candidates, message)
        return candidates[best_idx]["answer"]

    # ── VERIFICATION ────────────────────────────────────

    def _verify(self, question: str, answer: str) -> bool:
        """Cheap verifier: does the answer actually address the question?"""
        resp = self._llm([
            {"role": "system", "content": (
                "You are a verifier. Does the answer address the question? "
                "Reply ONLY: sufficient, unsupported, or contradictory."
            )},
            {"role": "user", "content": f"Question: {question}\nAnswer: {answer}"}
        ])
        return "sufficient" in resp.lower() if resp else True

    # ── PLANNING ────────────────────────────────────────

    def _plan(self, goal: str, mode: str = "chat") -> dict:
        # Filter tools based on mode/aperture
        available_tools = self._get_tools_for_mode(mode)
        tool_list = ", ".join(available_tools)
        
        resp = self._llm([
            {"role": "system", "content": (
                f"You are a planner in {mode.upper()} mode. Break the goal into max 3 steps. "
                f"Available tools: {tool_list}, none. "
                'Reply JSON ONLY: {"goal":"...","steps":[{"id":1,"description":"...","tool":"web_search","args":"..."}]}'
            )},
            {"role": "user", "content": goal}
        ])
        return self._extract_json(resp)

    # ── TOOL EXECUTION ──────────────────────────────────

    def _execute_tool(self, tool_name: str, args, chat_id: str = "default") -> str:
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
        args_str = args
        if isinstance(args, dict):
            # Handle special cases for different tools
            if tool_name == "file_write":
                args_str = f"{args.get('filename', '')}|||{args.get('content', '')}"
            elif tool_name == "web_fetch":
                args_str = args.get('url', '')
            elif tool_name == "http":
                # HTTP tool expects JSON string
                args_str = json.dumps(args)
            else:
                # For other tools, try to extract the first value or convert to JSON string
                args_str = str(args.get('args', '') or args.get('query', '') or list(args.values())[0] if args else '')
        
        result = tool.execute(str(args_str))
        
        # Self-healing: Check if tool execution failed
        if not result.success:
            logger.warning(f"Tool '{tool_name}' failed: {result.output[:100]}")
            self.self_healer.log_error(chat_id, result.output, f"Tool: {tool_name}, Args: {args_str}", tool_name)
            
            # Mark tool for potential disabling if failing repeatedly
            self.self_healer.should_disable_tool(tool_name, threshold=5)
        
        # Log tool usage to memory
        self.memory.log_tool_use(chat_id, tool_name, str(args_str), result.output)
        
        return result.output

    # ── LLM CALL ────────────────────────────────────────

    def _llm(self, messages: list) -> str:
        try:
            # Try OpenAI-compatible endpoint first (Groq, OpenAI, etc.)
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
            # Fallback: try Anthropic-compatible /v1/messages endpoint
            try:
                system_text = ""
                api_messages = []
                for m in messages:
                    if m["role"] == "system":
                        system_text += m["content"] + "\n"
                    else:
                        api_messages.append({"role": m["role"], "content": m["content"]})
                if not api_messages:
                    api_messages = [{"role": "user", "content": system_text.strip()}]
                    system_text = ""

                body = {"model": self.model, "max_tokens": 1024, "messages": api_messages}
                if system_text.strip():
                    body["system"] = system_text.strip()

                resp = http_requests.post(
                    f"{self.api_base}/messages", json=body, timeout=60,
                    headers={"Content-Type": "application/json", "anthropic-version": "2023-06-01", "x-api-key": self.api_key or "none"}
                )
                resp.raise_for_status()
                text = "".join(b.get("text", "") for b in resp.json().get("content", []) if b.get("type") == "text")
                return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
            except Exception as e2:
                logger.error(f"Anthropic fallback also failed: {e2}")
                return ""

    # ── UTILITIES ───────────────────────────────────────

    def _extract_json(self, text: str) -> dict:
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = text.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(text)
        except:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
        return {"goal": text, "steps": []}

    def _clean(self, text: str) -> str:
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        return text.replace("```json", "").replace("```", "").strip()
    
    # ── PHASE 4: INTELLIGENCE AMPLIFICATION ────────────

    def _classify_mode(self, message: str) -> str:
        """
        Classify operating mode based on message content
        Modes: chat, research, code, memory
        """
        msg_lower = message.lower()
        
        # Research mode keywords (check first — URLs and fetch are research, not code)
        if any(kw in msg_lower for kw in ["http", "https", "fetch", "summarize", "research", "search", "find", "investigate", "what is", "tell me about", "news", "latest"]):
            return "research"

        # Code mode keywords
        if any(kw in msg_lower for kw in ["file", "code", "write", "read", "script", "shell"]):
            return "research"
        
        # Memory mode keywords
        if any(kw in msg_lower for kw in ["remember", "recall", "my name", "what do you know"]):
            return "memory"
        
        # Default: chat mode
        return "chat"
    
    def _get_mode_prompt(self, mode: str) -> str:
        """Get system prompt for specific operating mode"""
        prompts = {
            "chat": "You are a helpful assistant. Be conversational and friendly.",
            "research": "You are a research assistant. Be thorough, cite sources, synthesize information clearly.",
            "code": "You are a code assistant. Be precise, test before delivering, explain your work.",
            "memory": "You are a memory keeper. Store facts accurately, recall them reliably."
        }
        return prompts.get(mode, prompts["chat"])
    
    def _get_tools_for_mode(self, mode: str) -> list:
        """Filter tools based on operating mode (aperture specialization)"""
        # Always include all tools — let the planner pick.
        # Mode just influences the system prompt tone, not tool availability.
        return list(self.tools.keys())
    
    def _check_evidence_sufficiency(self, question: str, evidence: list) -> bool:
        """
        Ask LLM: Is this evidence sufficient to answer the question?
        Returns True if sufficient, False if need more retrieval
        """
        if not evidence:
            return False
        
        evidence_text = "\n- ".join(evidence[:5])  # Max 5 pieces
        resp = self._llm([
            {"role": "system", "content": (
                "You are an evidence evaluator. Is this evidence sufficient to answer the question? "
                "Reply ONLY: yes or no."
            )},
            {"role": "user", "content": f"Question: {question}\n\nEvidence:\n{evidence_text}"}
        ])
        
        return "yes" in resp.lower()
    
    def _get_diverse_evidence(self, message: str, mode: str, num_sets: int = 3) -> list:
        """
        Get N different evidence sets by varying search queries/approaches
        Used for improved committee-of-clones in hard lane
        """
        evidence_sets = []
        
        # Generate diverse search strategies
        strategies = [
            f"{message}",
            f"{message} comprehensive guide",
            f"{message} expert perspective"
        ]
        
        for strategy in strategies[:num_sets]:
            # Quick plan for this strategy
            plan = self._plan(strategy, mode)
            results = []
            
            # Execute up to 2 steps
            for step in plan.get("steps", [])[:2]:
                tool = step.get("tool", "none")
                if tool == "none":
                    continue
                try:
                    result = self._execute_tool(tool, step.get("args", ""), "default")
                    results.append(result[:300])  # Truncate to 300 chars
                except Exception as e:
                    logger.error(f"Evidence gathering failed: {e}")
            
            evidence_sets.append(results)
        
        return evidence_sets
    
    def _score_candidates(self, candidates: list, question: str) -> int:
        """
        Deterministic scoring based on evidence coverage
        Returns index of best candidate
        """
        scores = []
        
        for candidate in candidates:
            score = 0
            answer = candidate["answer"]
            evidence = candidate.get("evidence", [])
            
            # Length penalty (too short = incomplete)
            if len(answer) < 50:
                score -= 2
            
            # Evidence citation bonus
            for ev in evidence:
                if any(word in answer.lower() for word in ev[:50].lower().split()):
                    score += 1
            
            # Completeness check (does it seem like a full answer?)
            if any(word in answer.lower() for word in ["because", "since", "therefore", "thus"]):
                score += 1
            
            scores.append(score)
        
        # Return index of highest score
        return scores.index(max(scores))
