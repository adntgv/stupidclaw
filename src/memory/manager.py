"""
Memory Manager — Orchestrates all 4 memory tiers
"""
import logging
from typing import Optional
from .hot import HotMemory
from .semantic import SemanticMemory
from .episodic import EpisodicMemory
from .procedural import ProceduralMemory

logger = logging.getLogger(__name__)


class MemoryManager:
    """Combines all 4 memory tiers: hot, semantic, episodic, procedural"""
    
    def __init__(self, data_dir: str = "/app/data"):
        self.hot = HotMemory(max_tokens=2000, persist_path=f"{data_dir}/hot_memory.json")
        self.semantic = SemanticMemory(persist_dir=f"{data_dir}/chromadb")
        self.episodic = EpisodicMemory(data_dir=f"{data_dir}/episodes")
        self.procedural = ProceduralMemory(data_dir=data_dir)
    
    def add_user_message(self, chat_id: str, message: str):
        """Log a user message across tiers"""
        # Hot memory
        self.hot.add_message(chat_id, "user", message)
        
        # Episodic log
        self.episodic.log_event("user_message", {
            "chat_id": chat_id,
            "message": message
        })
    
    def add_bot_response(self, chat_id: str, response: str):
        """Log a bot response across tiers"""
        # Hot memory
        self.hot.add_message(chat_id, "assistant", response)
        
        # Episodic log
        self.episodic.log_event("bot_response", {
            "chat_id": chat_id,
            "response": response
        })
    
    def store_fact(self, chat_id: str, fact: str, metadata: Optional[dict] = None):
        """Store a long-term fact in BOTH hot memory (instant) and ChromaDB (eventual)"""
        # Hot memory FIRST (instant recall)
        self.hot.store_fact(chat_id, fact)
        
        # Semantic memory (eventual consistency)
        self.semantic.store(chat_id, fact, metadata)
        
        # Also update procedural MEMORY.md
        self.procedural.update_memory(fact)
        
        # Log event
        self.episodic.log_event("fact_stored", {
            "chat_id": chat_id,
            "fact": fact
        })
    
    def log_tool_use(self, chat_id: str, tool_name: str, args: str, result: str):
        """Log tool execution"""
        self.episodic.log_event("tool_use", {
            "chat_id": chat_id,
            "tool": tool_name,
            "args": args,
            "result": result[:200]
        })
    
    def log_error(self, chat_id: str, error: str, context: str):
        """Log an error"""
        self.episodic.log_event("error", {
            "chat_id": chat_id,
            "error": error,
            "context": context
        })
    
    def build_context(self, chat_id: str, query: str, budget: int = 3000) -> str:
        """
        Build memory context for LLM injection
        Pull-based: returns summary index first, not everything
        """
        parts = []
        remaining_budget = budget
        
        # 1. Procedural memory (always included, ~1000 chars)
        procedural = self.procedural.compress_for_context(max_chars=1000)
        parts.append(f"# SYSTEM KNOWLEDGE\n{procedural}")
        remaining_budget -= len(procedural)
        
        # 2. Hot memory (recent conversation, ~800 chars)
        hot_history = self.hot.get_formatted_history(chat_id)
        if hot_history:
            hot_summary = hot_history[:800]
            parts.append(f"\n# RECENT CONVERSATION\n{hot_summary}")
            remaining_budget -= len(hot_summary)
        
        # 2b. Hot memory facts (INSTANT recall, ~400 chars)
        hot_facts = self.hot.recall_facts(chat_id)
        if hot_facts:
            facts_text = "\n- " + "\n- ".join(hot_facts)
            facts_section = f"\n# KNOWN FACTS (INSTANT){facts_text}"[:400]
            parts.append(facts_section)
            remaining_budget -= len(facts_section)
        
        # 3. Semantic recall (relevant facts, ~600 chars)
        if remaining_budget > 0:
            relevant_facts = self.semantic.recall(chat_id, query, limit=5)
            if relevant_facts:
                facts_text = "\n- " + "\n- ".join(f[:100] for f in relevant_facts[:5])
                parts.append(f"\n# RELEVANT FACTS{facts_text}")
                remaining_budget -= len(facts_text)
        
        # 4. Recent episodic events (if budget allows, ~400 chars)
        if remaining_budget > 400:
            recent_errors = self.episodic.get_errors(days=3)
            if recent_errors:
                error_summary = f"\n# RECENT ERRORS ({len(recent_errors)} in last 3 days)"
                parts.append(error_summary)
        
        return "\n".join(parts)[:budget]
    
    def summarize_conversation(self, chat_id: str, llm_call):
        """Compress hot memory using LLM summarization"""
        return self.hot.summarize(chat_id, llm_call)
