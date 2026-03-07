"""
Git Tool — Safe git operations in sandboxed directory
"""
import subprocess
import shlex
from pathlib import Path
from src.tools.base import BaseTool, ToolResult

# Allowlisted git commands
ALLOWED_COMMANDS = {
    "status", "add", "commit", "push", "pull", 
    "log", "diff", "branch", "checkout"
}

# Sandboxed working directory
WORKING_DIR = "/app/data/repos"


class GitTool(BaseTool):
    name = "git"
    description = "Run safe git commands in /app/data/repos/. Allowed: status, add, commit, push, pull, log, diff, branch, checkout"
    args_description = "git command (e.g., 'status', 'add .', 'commit -m \"message\"')"
    
    def __init__(self):
        super().__init__()
        # Ensure repos directory exists
        Path(WORKING_DIR).mkdir(parents=True, exist_ok=True)
    
    def execute(self, args: str) -> ToolResult:
        try:
            # Parse command
            parts = shlex.split(args.strip())
            if not parts:
                return ToolResult(False, "Empty git command")
            
            # Check first word (git subcommand)
            cmd = parts[0]
            if cmd not in ALLOWED_COMMANDS:
                return ToolResult(
                    False, 
                    f"Git command '{cmd}' not allowed. Permitted: {', '.join(sorted(ALLOWED_COMMANDS))}"
                )
            
            # Build full git command
            full_cmd = f"git {args.strip()}"
            
            # Execute in sandboxed directory
            result = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=WORKING_DIR
            )
            
            # Combine stdout and stderr
            output = (result.stdout + result.stderr).strip()
            
            # Truncate long output
            if len(output) > 4000:
                output = output[:4000] + "\n... (truncated)"
            
            success = result.returncode == 0
            return ToolResult(success, output or "(no output)")
        
        except subprocess.TimeoutExpired:
            return ToolResult(False, "Git command timed out (30s limit)")
        except Exception as e:
            return ToolResult(False, f"Git error: {e}")
