"""
Hot Memory — Recent conversation history with sliding window + compression
Also stores key facts in-memory for instant recall (no ChromaDB lag)
"""
import logging
from typing import List, Dict
from collections import defaultdict

logger = logging.getLogger(__name__)


class HotMemory:
    """Stores last N messages per user with token-based sliding window + instant fact cache"""
    
    def __init__(self, max_tokens: int = 2000):
        self.max_tokens = max_tokens
        self.conversations: Dict[str, List[Dict]] = defaultdict(list)
        self.facts: Dict[str, List[str]] = defaultdict(list)  # Instant fact cache
    
    def add_message(self, chat_id: str, role: str, content: str):
        """Add a message to conversation history"""
        msg = {"role": role, "content": content}
        self.conversations[chat_id].append(msg)
        self._trim_to_budget(chat_id)
    
    def get_history(self, chat_id: str, max_messages: int = 20) -> List[Dict]:
        """Get recent conversation history"""
        return self.conversations[chat_id][-max_messages:]
    
    def get_formatted_history(self, chat_id: str) -> str:
        """Return formatted conversation history for context injection"""
        history = self.conversations.get(chat_id, [])
        if not history:
            return ""
        
        lines = []
        for msg in history[-10:]:  # Last 10 messages
            role = msg['role'].upper()
            lines.append(f"{role}: {msg['content'][:200]}")
        
        return "\n".join(lines)
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate: len(text) // 4"""
        return len(text) // 4
    
    def _trim_to_budget(self, chat_id: str):
        """Remove oldest messages if over token budget"""
        messages = self.conversations[chat_id]
        total_tokens = sum(self._estimate_tokens(m['content']) for m in messages)
        
        while total_tokens > self.max_tokens and len(messages) > 1:
            removed = messages.pop(0)
            total_tokens -= self._estimate_tokens(removed['content'])
    
    def summarize(self, chat_id: str, llm_call) -> str:
        """
        Summarize old conversation history using LLM
        llm_call: function(messages: List[Dict]) -> str
        """
        history = self.conversations.get(chat_id, [])
        if len(history) < 5:
            return ""
        
        # Get first half of conversation to summarize
        to_summarize = history[:len(history)//2]
        
        try:
            summary_prompt = [
                {"role": "system", "content": "Summarize this conversation in 2-3 sentences. Focus on key facts and decisions."},
                {"role": "user", "content": "\n".join(f"{m['role']}: {m['content']}" for m in to_summarize)}
            ]
            summary = llm_call(summary_prompt)
            
            # Replace old messages with summary
            self.conversations[chat_id] = [
                {"role": "system", "content": f"[Previous conversation summary: {summary}]"}
            ] + history[len(history)//2:]
            
            return summary
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return ""
    
    def clear(self, chat_id: str):
        """Clear conversation history for a user"""
        if chat_id in self.conversations:
            del self.conversations[chat_id]
    
    def store_fact(self, chat_id: str, fact: str):
        """Store a fact in hot memory for instant recall (no ChromaDB lag)"""
        self.facts[chat_id].append(fact)
        # Keep only last 20 facts per user
        if len(self.facts[chat_id]) > 20:
            self.facts[chat_id] = self.facts[chat_id][-20:]
        logger.info(f"Stored fact in hot memory: {fact[:50]}")
    
    def recall_facts(self, chat_id: str) -> List[str]:
        """Get all facts stored in hot memory for instant recall"""
        return self.facts.get(chat_id, [])
