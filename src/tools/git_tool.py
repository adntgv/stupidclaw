"""
Git Tool — Safe git operations for self-modification and repos
"""
import subprocess
import shlex
import os
from pathlib import Path
from src.tools.base import BaseTool, ToolResult

# Allowlisted git commands
ALLOWED_COMMANDS = {
    "status", "add", "commit", "push", "pull", 
    "log", "diff", "branch", "checkout", "config"
}

# Self-modification repo
SELF_REPO = "/app"


class GitTool(BaseTool):
    name = "git"
    description = "Run git commands for self-modification. Works in /app (your source code). Allowed: status, add, commit, push, pull, log, diff, branch, checkout, config"
    args_description = "git command (e.g., 'status', 'add src/agent.py', 'commit -m \"Self-mod: fix\"', 'push')"
    
    def __init__(self):
        super().__init__()
        # Set git config for commits if not already set
        self._ensure_git_config()
    
    def _ensure_git_config(self):
        """Ensure git has user.name and user.email configured"""
        try:
            # Check if config exists
            result = subprocess.run(
                ["git", "config", "user.name"],
                capture_output=True,
                cwd=SELF_REPO,
                timeout=5
            )
            if result.returncode != 0:
                # Set default config for bot commits
                subprocess.run(
                    ["git", "config", "user.name", "StupidClaw Bot"],
                    cwd=SELF_REPO,
                    timeout=5
                )
                subprocess.run(
                    ["git", "config", "user.email", "stupidclaw@localhost"],
                    cwd=SELF_REPO,
                    timeout=5
                )
        except:
            pass  # Config will fail if not in a git repo, that's ok
    
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
            
            # Execute in /app (the bot's source repo)
            result = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=SELF_REPO
            )
            
            # Combine stdout and stderr
            output = (result.stdout + result.stderr).strip()
            
            # Truncate long output
            if len(output) > 2000:
                output = output[:2000] + "\n... (truncated)"
            
            success = result.returncode == 0
            return ToolResult(success, output or "(no output)")
        
        except subprocess.TimeoutExpired:
            return ToolResult(False, "Git command timed out (30s limit)")
        except Exception as e:
            return ToolResult(False, f"Git error: {e}")
