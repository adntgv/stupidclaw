"""
Self-Healing Loop — Error detection, retry logic, and pattern analysis
"""
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

ERROR_INDICATORS = [
    "error", "failed", "unable to", "could not", "cannot",
    "exception", "timeout", "not found", "invalid", "forbidden"
]

class SelfHealer:
    """Detects errors, retries with alternative approaches, learns from patterns"""
    
    def __init__(self, data_dir: str = "/app/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.errors_file = self.data_dir / "errors.jsonl"
        self.lessons_file = self.data_dir / "lessons.jsonl"
        self.disabled_tools = {}  # tool_name -> disabled_at timestamp
        self.message_count = 0
        self.error_patterns = {}
        
    def is_tool_disabled(self, tool_name: str) -> bool:
        """Check if tool is disabled, re-enable after 5 minute cooldown"""
        if tool_name not in self.disabled_tools:
            return False
        disabled_at = self.disabled_tools[tool_name]
        if (datetime.now() - disabled_at).total_seconds() > 300:  # 5 min cooldown
            del self.disabled_tools[tool_name]
            self.error_patterns.pop(tool_name, None)
            logger.info(f"Tool '{tool_name}' re-enabled after cooldown")
            return False
        return True

    def check_for_errors(self, response: str) -> bool:
        """Check if response contains error indicators"""
        response_lower = response.lower()
        return any(indicator in response_lower for indicator in ERROR_INDICATORS)
    
    def log_error(self, chat_id: str, error_msg: str, user_message: str, 
                  tool_name: Optional[str] = None):
        """Log error to errors.jsonl"""
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "chat_id": chat_id,
            "error": error_msg,
            "user_message": user_message[:200],
            "tool": tool_name
        }
        
        with open(self.errors_file, "a") as f:
            f.write(json.dumps(error_entry) + "\n")
        
        # Track patterns
        if tool_name:
            self.error_patterns[tool_name] = self.error_patterns.get(tool_name, 0) + 1
        
        logger.warning(f"Error logged: {error_msg[:100]}")
    
    def store_lesson(self, lesson: str, context: str):
        """Store a lesson learned to lessons.jsonl"""
        lesson_entry = {
            "timestamp": datetime.now().isoformat(),
            "lesson": lesson,
            "context": context
        }
        
        with open(self.lessons_file, "a") as f:
            f.write(json.dumps(lesson_entry) + "\n")
        
        logger.info(f"Lesson stored: {lesson[:100]}")
    
    def analyze_patterns(self) -> Dict[str, int]:
        """Analyze error patterns from errors.jsonl"""
        if not self.errors_file.exists():
            return {}
        
        patterns = {}
        with open(self.errors_file, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    tool = entry.get("tool")
                    if tool:
                        patterns[tool] = patterns.get(tool, 0) + 1
                except:
                    continue
        
        return patterns
    
    def should_disable_tool(self, tool_name: str, threshold: int = 5) -> bool:
        """Check if a tool should be disabled due to repeated failures"""
        patterns = self.analyze_patterns()
        failures = patterns.get(tool_name, 0)
        
        if failures >= threshold and tool_name not in self.disabled_tools:
            self.disabled_tools[tool_name] = datetime.now()
            logger.warning(f"Tool '{tool_name}' disabled after {failures} failures (re-enables in 5 min)")
            self.store_lesson(
                f"Tool '{tool_name}' unreliable (>{threshold} failures)",
                f"Disabled after {failures} consecutive errors"
            )
            return True
        
        return False
    
    def get_alternative_tool(self, failed_tool: str, tools: dict) -> Optional[str]:
        """Suggest alternative tool based on the failed tool type"""
        alternatives = {
            "web_fetch": ["web_search"],
            "web_search": ["web_fetch"],
            "file_read": ["file_list", "shell"],
            "shell": ["file_read"],
        }
        
        candidates = alternatives.get(failed_tool, [])
        # Filter out disabled tools
        available = [t for t in candidates if t in tools and t not in self.disabled_tools]
        
        return available[0] if available else None
    
    def periodic_review(self):
        """Review errors periodically (called every N messages)"""
        self.message_count += 1
        
        # Review every 10 messages
        if self.message_count % 10 == 0:
            patterns = self.analyze_patterns()
            if patterns:
                logger.info(f"Error pattern review: {patterns}")
                
                # Disable tools with excessive failures
                for tool, count in patterns.items():
                    self.should_disable_tool(tool, threshold=5)
    
    def get_retry_strategy(self, original_plan: dict, failed_tool: str, 
                          available_tools: dict) -> Optional[dict]:
        """Generate a retry strategy with alternative tools"""
        alt_tool = self.get_alternative_tool(failed_tool, available_tools)
        
        if not alt_tool:
            return None
        
        # Modify plan to use alternative tool
        retry_plan = original_plan.copy()
        for step in retry_plan.get("steps", []):
            if step.get("tool") == failed_tool:
                step["tool"] = alt_tool
                # Modify args if needed (e.g., web_fetch URL -> web_search query)
                if failed_tool == "web_fetch" and alt_tool == "web_search":
                    url = step.get("args", "")
                    if url.startswith("http"):
                        # Extract domain for search
                        domain = re.search(r'https?://([^/]+)', url)
                        if domain:
                            step["args"] = f"site:{domain.group(1)}"
        
        logger.info(f"Retry strategy: replacing {failed_tool} with {alt_tool}")
        return retry_plan
    
    def _is_tool_disabled_old(self, tool_name: str) -> bool:
        """Deprecated — use is_tool_disabled at top of class"""
        return self.is_tool_disabled(tool_name)
    
    def get_lessons(self, limit: int = 10) -> List[str]:
        """Retrieve recent lessons learned"""
        if not self.lessons_file.exists():
            return []
        
        lessons = []
        with open(self.lessons_file, "r") as f:
            lines = f.readlines()
            for line in reversed(lines[-limit:]):
                try:
                    entry = json.loads(line)
                    lessons.append(entry["lesson"])
                except:
                    continue
        
        return lessons
