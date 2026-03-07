# src/tools/shell.py
import subprocess
import shlex
from src.tools.base import BaseTool, ToolResult

ALLOWED_COMMANDS = {
    "echo", "cat", "ls", "pwd", "whoami", "date",
    "curl", "wget", "git", "docker", "docker-compose",
    "pip", "python3", "grep", "wc", "head", "tail",
    "sort", "uniq", "find", "uname", "df", "du",
    "cut", "tr",
}

class ShellTool(BaseTool):
    name = "shell"
    description = "Run a shell command (allowlisted: ls, cat, head, tail, grep, python3, curl, etc). Max 10s timeout."
    args_description = "shell command string"

    def execute(self, args: str) -> ToolResult:
        try:
            # Split command properly: "docker ps" -> ["docker", "ps"]
            parts = shlex.split(args.strip())
            if not parts:
                return ToolResult(False, "Empty command")
            
            # Check FIRST word only (command name)
            cmd = parts[0].split("/")[-1]  # basename
            if cmd not in ALLOWED_COMMANDS:
                return ToolResult(False, f"Command '{cmd}' not in allowlist: {sorted(ALLOWED_COMMANDS)}")
            result = subprocess.run(
                args.strip(), shell=True, capture_output=True,
                text=True, timeout=10, cwd="/app/data"
            )
            output = (result.stdout + result.stderr).strip()
            return ToolResult(result.returncode == 0, output[:4000] or "(no output)")
        except subprocess.TimeoutExpired:
            return ToolResult(False, "Command timed out (10s limit)")
        except Exception as e:
            return ToolResult(False, f"Shell error: {e}")
