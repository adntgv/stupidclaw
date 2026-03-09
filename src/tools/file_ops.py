# src/tools/file_ops.py
import os
from pathlib import Path
from src.tools.base import BaseTool, ToolResult

SANDBOX = Path(os.environ.get("FILE_SANDBOX", "/app/data"))
ALLOWED_PATHS = [
    Path("/app/data"),  # Data directory
    Path("/app/src"),   # Source code (for self-modification)
    Path("/app")        # Root /app for reading SELF-MODIFY.md, etc.
]

def _safe_path(name: str) -> Path:
    """Resolve path, allow /app/data and /app/src for self-modification."""
    # Handle absolute paths starting with /app/
    if name.startswith("/app/"):
        p = Path(name).resolve()
    else:
        # Relative paths go to data sandbox
        p = (SANDBOX / name).resolve()
    
    # Check if path is within any allowed directory
    allowed = any(str(p).startswith(str(allowed_dir.resolve())) for allowed_dir in ALLOWED_PATHS)
    if not allowed:
        raise ValueError("Path escapes sandbox")
    return p

class FileReadTool(BaseTool):
    name = "file_read"
    description = "Read a file from /app/data or /app/src (for code). Returns content (max 4000 chars)."
    args_description = "filename (relative to /app/data, or absolute like /app/src/agent.py)"

    def execute(self, args: str) -> ToolResult:
        try:
            p = _safe_path(args.strip())
            if not p.exists():
                return ToolResult(False, "File not found")
            return ToolResult(True, p.read_text()[:4000])
        except Exception as e:
            return ToolResult(False, f"Read error: {e}")

class FileWriteTool(BaseTool):
    name = "file_write"
    description = "Write content to /app/data or /app/src (for self-modification). Creates dirs as needed."
    args_description = "filename|||content (triple pipe separator, filename can be absolute like /app/src/agent.py)"

    def execute(self, args: str) -> ToolResult:
        try:
            parts = args.split("|||", 1)
            if len(parts) != 2:
                return ToolResult(False, "Format: filename|||content")
            p = _safe_path(parts[0].strip())
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(parts[1])
            return ToolResult(True, f"Written {len(parts[1])} chars to {parts[0].strip()}")
        except Exception as e:
            return ToolResult(False, f"Write error: {e}")

class FileListTool(BaseTool):
    name = "file_list"
    description = "List files in the data directory."
    args_description = "subdirectory (optional, default root)"

    def execute(self, args: str) -> ToolResult:
        try:
            p = _safe_path(args.strip() or ".")
            if not p.is_dir():
                return ToolResult(False, "Not a directory")
            files = [str(f.relative_to(SANDBOX)) for f in sorted(p.rglob("*")) if f.is_file()]
            return ToolResult(True, "\n".join(files[:50]) or "(empty)")
        except Exception as e:
            return ToolResult(False, f"List error: {e}")
