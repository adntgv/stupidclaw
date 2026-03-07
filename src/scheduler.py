"""
Scheduler — Periodic task scheduling with APScheduler + cron management
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Manages periodic tasks, heartbeats, and cron jobs"""
    
    def __init__(self, data_dir: str = "/app/data"):
        self.scheduler = AsyncIOScheduler()
        self.tasks = {}
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.cron_log = self.data_dir / "cron.jsonl"
        
    def start(self):
        """Start the scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")
            
            # Add default jobs
            self._setup_default_jobs()
    
    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
    
    def _setup_default_jobs(self):
        """Setup default periodic jobs"""
        try:
            # 1. Error review every hour
            self.add_interval_task(
                "error_review",
                self._error_review_job,
                minutes=60
            )
            
            # 2. Health check every 30 minutes
            self.add_interval_task(
                "health_check",
                self._health_check_job,
                minutes=30
            )
            
            # 3. Memory consolidation every 6 hours
            self.add_interval_task(
                "memory_consolidation",
                self._memory_consolidation_job,
                minutes=360
            )
            
            logger.info("Default jobs configured")
        except Exception as e:
            logger.error(f"Failed to setup default jobs: {e}")
    
    def add_daily_task(self, task_id: str, func, hour: int = 0, minute: int = 0):
        """Add a task that runs daily at a specific time"""
        trigger = CronTrigger(hour=hour, minute=minute)
        job = self.scheduler.add_job(
            func,
            trigger=trigger,
            id=task_id,
            replace_existing=True
        )
        self.tasks[task_id] = {
            "job": job,
            "type": "daily",
            "schedule": f"{hour:02d}:{minute:02d}"
        }
        logger.info(f"Added daily task '{task_id}' at {hour:02d}:{minute:02d}")
    
    def add_interval_task(self, task_id: str, func, minutes: int):
        """Add a task that runs every N minutes"""
        job = self.scheduler.add_job(
            func,
            IntervalTrigger(minutes=minutes),
            id=task_id,
            replace_existing=True
        )
        self.tasks[task_id] = {
            "job": job,
            "type": "interval",
            "schedule": f"every {minutes} minutes"
        }
        logger.info(f"Added interval task '{task_id}' every {minutes} minutes")
    
    def remove_task(self, task_id: str) -> bool:
        """Remove a scheduled task"""
        if task_id in self.tasks:
            try:
                self.scheduler.remove_job(task_id)
                del self.tasks[task_id]
                logger.info(f"Removed task '{task_id}'")
                return True
            except Exception as e:
                logger.error(f"Failed to remove task '{task_id}': {e}")
                return False
        return False
    
    def list_tasks(self) -> dict:
        """List all scheduled tasks with their schedules"""
        result = {}
        for task_id, info in self.tasks.items():
            result[task_id] = {
                "type": info["type"],
                "schedule": info["schedule"],
                "next_run": str(info["job"].next_run_time) if info["job"].next_run_time else "N/A"
            }
        return result
    
    def _log_cron_result(self, job_name: str, status: str, message: str):
        """Log cron job result to cron.jsonl"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "job": job_name,
            "status": status,
            "message": message
        }
        
        with open(self.cron_log, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    # ── Default Jobs ────────────────────────────────────
    
    async def _error_review_job(self):
        """Review errors.jsonl for patterns"""
        try:
            errors_file = self.data_dir / "errors.jsonl"
            if not errors_file.exists():
                self._log_cron_result("error_review", "success", "No errors found")
                return
            
            # Count errors by tool
            patterns = {}
            with open(errors_file, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        tool = entry.get("tool", "unknown")
                        patterns[tool] = patterns.get(tool, 0) + 1
                    except:
                        continue
            
            if patterns:
                msg = f"Error patterns: {json.dumps(patterns)}"
                logger.info(msg)
                self._log_cron_result("error_review", "success", msg)
            else:
                self._log_cron_result("error_review", "success", "No error patterns detected")
                
        except Exception as e:
            error_msg = f"Error review failed: {e}"
            logger.error(error_msg)
            self._log_cron_result("error_review", "failed", error_msg)
    
    async def _health_check_job(self):
        """Verify bot can reach Groq API"""
        try:
            import os
            import requests as http_requests
            
            base_url = os.getenv("OPENAI_BASE_URL", "").rstrip("/")
            api_key = os.getenv("OPENAI_API_KEY", "none")
            model = os.getenv("MODEL_NAME", "MiniMax-M2.5")
            
            if not base_url:
                raise ValueError("Missing OPENAI_BASE_URL")
            
            # Quick API ping via Anthropic-compatible endpoint
            resp = http_requests.post(
                f"{base_url}/messages",
                json={"model": model, "max_tokens": 10, "messages": [{"role": "user", "content": "ping"}]},
                headers={"Content-Type": "application/json", "anthropic-version": "2023-06-01", "x-api-key": api_key},
                timeout=15
            )
            resp.raise_for_status()
            
            if resp.json().get("content"):
                self._log_cron_result("health_check", "success", "API reachable")
            else:
                self._log_cron_result("health_check", "warning", "API response unexpected")
                
        except Exception as e:
            error_msg = f"Health check failed: {e}"
            logger.error(error_msg)
            self._log_cron_result("health_check", "failed", error_msg)
    
    async def _memory_consolidation_job(self):
        """Summarize hot memory into MEMORY.md"""
        try:
            # Check if we have episodes to consolidate
            episodes_dir = self.data_dir / "episodes"
            if not episodes_dir.exists():
                self._log_cron_result("memory_consolidation", "success", "No episodes to consolidate")
                return
            
            # Count episode files
            episode_files = list(episodes_dir.glob("*.json"))
            
            if episode_files:
                msg = f"Found {len(episode_files)} episodes (consolidation logic TBD)"
                logger.info(msg)
                self._log_cron_result("memory_consolidation", "success", msg)
            else:
                self._log_cron_result("memory_consolidation", "success", "No new episodes")
                
        except Exception as e:
            error_msg = f"Memory consolidation failed: {e}"
            logger.error(error_msg)
            self._log_cron_result("memory_consolidation", "failed", error_msg)
