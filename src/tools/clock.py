# src/tools/clock.py
from datetime import datetime
from src.tools.base import BaseTool, ToolResult

class ClockTool(BaseTool):
    name = "time"
    description = "Get the current date and time (UTC)."
    args_description = "(none)"

    def execute(self, args: str) -> ToolResult:
        return ToolResult(True, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))
