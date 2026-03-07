"""
Procedural Memory — System knowledge from markdown files (SOUL, USER, MEMORY)
"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ProceduralMemory:
    """Reads and manages procedural knowledge from markdown files"""
    
    def __init__(self, data_dir: str = "/app/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.soul_path = self.data_dir / "SOUL.md"
        self.user_path = self.data_dir / "USER.md"
        self.memory_path = self.data_dir / "MEMORY.md"
        
        # Initialize files if they don't exist
        self._init_files()
    
    def _init_files(self):
        """Create default files if they don't exist"""
        if not self.soul_path.exists():
            self.soul_path.write_text(
                "# SOUL.md - Bot Identity\n\n"
                "I am StupidClaw - a cheap, strict, tool-reliant assistant.\n"
                "I follow the cascade architecture and always verify my answers.\n"
            )
        
        if not self.user_path.exists():
            self.user_path.write_text(
                "# USER.md - User Preferences\n\n"
                "No user preferences stored yet.\n"
            )
        
        if not self.memory_path.exists():
            self.memory_path.write_text(
                "# MEMORY.md - Long-term Facts\n\n"
                "No facts stored yet.\n"
            )
    
    def get_soul(self) -> str:
        """Get bot identity/instructions"""
        try:
            return self.soul_path.read_text()
        except Exception as e:
            logger.error(f"Failed to read SOUL.md: {e}")
            return ""
    
    def get_user_info(self) -> str:
        """Get user preferences and information"""
        try:
            return self.user_path.read_text()
        except Exception as e:
            logger.error(f"Failed to read USER.md: {e}")
            return ""
    
    def get_memory(self) -> str:
        """Get long-term facts and knowledge"""
        try:
            return self.memory_path.read_text()
        except Exception as e:
            logger.error(f"Failed to read MEMORY.md: {e}")
            return ""
    
    def update_memory(self, fact: str):
        """Append a fact to MEMORY.md"""
        try:
            with self.memory_path.open('a', encoding='utf-8') as f:
                f.write(f"\n- {fact}\n")
            logger.info(f"Updated MEMORY.md with: {fact[:50]}")
        except Exception as e:
            logger.error(f"Failed to update MEMORY.md: {e}")
    
    def update_user_info(self, info: str):
        """Append user information to USER.md"""
        try:
            with self.user_path.open('a', encoding='utf-8') as f:
                f.write(f"\n- {info}\n")
            logger.info(f"Updated USER.md with: {info[:50]}")
        except Exception as e:
            logger.error(f"Failed to update USER.md: {e}")
    
    def compress_for_context(self, max_chars: int = 1000) -> str:
        """Get compressed version of all procedural memory for injection"""
        soul = self.get_soul()[:300]
        user = self.get_user_info()[:300]
        memory = self.get_memory()[:400]
        
        context = f"# IDENTITY\n{soul}\n\n# USER\n{user}\n\n# FACTS\n{memory}"
        return context[:max_chars]
