"""
Docker Tool — Safe Docker operations (ps, logs, restart, compose)
"""
import subprocess
import shlex
from src.tools.base import BaseTool, ToolResult

# Allowlisted Docker commands (pattern-based for safety)
ALLOWED_PATTERNS = [
    "docker ps",
    "docker logs",
    "docker restart",
    "docker-compose up -d",
    "docker-compose down",
    "docker compose up -d",
    "docker compose down"
]

class DockerTool(BaseTool):
    name = "docker"
    description = "Run safe Docker commands: ps, logs <container> --tail 20, restart <container>, compose up/down"
    args_description = "docker command (allowlisted: ps, logs, restart, compose up/down)"
    
    def _is_allowed(self, cmd: str) -> bool:
        """Check if command matches allowed patterns"""
        cmd_lower = cmd.lower().strip()
        
        # Check if command starts with any allowed pattern
        for pattern in ALLOWED_PATTERNS:
            if cmd_lower.startswith(pattern):
                # Additional safety checks
                if "exec" in cmd_lower or "rm " in cmd_lower or "rmi" in cmd_lower:
                    return False
                return True
        
        return False
    
    def execute(self, args: str) -> ToolResult:
        try:
            cmd = args.strip()
            
            # Auto-prepend "docker" if not present
            if not cmd.startswith("docker"):
                cmd = f"docker {cmd}"
            
            # Security check
            if not self._is_allowed(cmd):
                return ToolResult(
                    False, 
                    f"Command not allowed. Permitted: {', '.join(ALLOWED_PATTERNS)}"
                )
            
            # Special handling for logs to limit output
            if "docker logs" in cmd and "--tail" not in cmd:
                cmd += " --tail 20"
            
            # Run command
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd="/app"
            )
            
            output = (result.stdout + result.stderr).strip()
            
            # Truncate to 4000 chars
            if len(output) > 4000:
                output = output[:4000] + "\n... (truncated)"
            
            success = result.returncode == 0
            return ToolResult(success, output or "(no output)")
            
        except subprocess.TimeoutExpired:
            return ToolResult(False, "Command timed out (30s limit)")
        except Exception as e:
            return ToolResult(False, f"Docker error: {e}")
