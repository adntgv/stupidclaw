"""
Skill Loader — Discovers and loads skills from SKILL.md files
"""
import logging
import re
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class SkillLoader:
    """Scans skills directory and matches skills by keywords"""
    
    def __init__(self, skills_dir: str = "/app/skills"):
        self.skills_dir = Path(skills_dir)
        self.skills: Dict[str, Dict] = {}
        self.load_all_skills()
    
    def load_all_skills(self):
        """Scan skills directory and load all SKILL.md files"""
        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            return
        
        for skill_path in self.skills_dir.glob("*/SKILL.md"):
            try:
                skill = self._parse_skill_file(skill_path)
                if skill:
                    self.skills[skill['name']] = skill
                    logger.info(f"Loaded skill: {skill['name']}")
            except Exception as e:
                logger.error(f"Failed to load skill {skill_path}: {e}")
    
    def _parse_skill_file(self, path: Path) -> Optional[Dict]:
        """Parse a SKILL.md file and extract metadata"""
        content = path.read_text()
        
        # Extract fields using simple regex
        name = self._extract_field(content, "name")
        description = self._extract_field(content, "description")
        triggers = self._extract_list(content, "triggers")
        tools_needed = self._extract_list(content, "tools_needed")
        prompt_template = self._extract_section(content, "prompt_template")
        
        if not name:
            logger.warning(f"Skill file missing name: {path}")
            return None
        
        return {
            "name": name,
            "description": description or "",
            "triggers": triggers,
            "tools_needed": tools_needed,
            "prompt_template": prompt_template or "",
            "path": str(path.parent)
        }
    
    def _extract_field(self, content: str, field: str) -> str:
        """Extract a single field value"""
        pattern = rf"^{field}:\s*(.+)$"
        match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
        return match.group(1).strip() if match else ""
    
    def _extract_list(self, content: str, field: str) -> List[str]:
        """Extract a comma-separated list field"""
        value = self._extract_field(content, field)
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]
    
    def _extract_section(self, content: str, section: str) -> str:
        """Extract a markdown section"""
        pattern = rf"## {section}[:\s]*\n(.+?)(?=\n##|\Z)"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""
    
    def match_skill(self, query: str) -> Optional[Dict]:
        """Find best matching skill based on triggers"""
        query_lower = query.lower()
        
        for skill in self.skills.values():
            for trigger in skill['triggers']:
                if trigger.lower() in query_lower:
                    logger.info(f"Matched skill: {skill['name']} (trigger: {trigger})")
                    return skill
        
        return None
    
    def get_skill(self, name: str) -> Optional[Dict]:
        """Get a specific skill by name"""
        return self.skills.get(name)
    
    def list_skills(self) -> List[str]:
        """List all available skill names"""
        return list(self.skills.keys())
