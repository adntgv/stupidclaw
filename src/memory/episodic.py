"""
Episodic Memory — Event logs in daily JSONL files
"""
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict

logger = logging.getLogger(__name__)


class EpisodicMemory:
    """Stores events in daily JSONL logs for temporal recall"""
    
    def __init__(self, data_dir: str = "/app/data/episodes"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_log_path(self, date: datetime = None) -> Path:
        """Get path to log file for a specific date"""
        if date is None:
            date = datetime.now()
        filename = date.strftime("%Y-%m-%d.jsonl")
        return self.data_dir / filename
    
    def log_event(self, event_type: str, data: Dict):
        """
        Log an event to today's file
        Types: user_message, bot_response, tool_use, error
        """
        try:
            log_path = self._get_log_path()
            event = {
                "timestamp": datetime.now().isoformat(),
                "type": event_type,
                "data": data
            }
            
            with log_path.open('a', encoding='utf-8') as f:
                f.write(json.dumps(event) + '\n')
        except Exception as e:
            logger.error(f"Failed to log event: {e}")
    
    def recall_recent(self, days: int = 7) -> List[Dict]:
        """Retrieve events from the last N days"""
        events = []
        
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            log_path = self._get_log_path(date)
            
            if not log_path.exists():
                continue
            
            try:
                with log_path.open('r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            events.append(json.loads(line))
            except Exception as e:
                logger.error(f"Failed to read log {log_path}: {e}")
        
        return events
    
    def get_events_by_type(self, event_type: str, days: int = 7) -> List[Dict]:
        """Get all events of a specific type from recent days"""
        all_events = self.recall_recent(days)
        return [e for e in all_events if e.get('type') == event_type]
    
    def get_errors(self, days: int = 7) -> List[Dict]:
        """Get all error events from recent days"""
        return self.get_events_by_type('error', days)
