"""
Telegram Bridge Tool — Send/receive messages via OpenClaw Telegram bridge
"""
import requests
import logging
from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

BRIDGE_URL = "http://10.0.0.1:18800"
BEARER_TOKEN = "X_K6rjUFN1YGNUHXWxRWlA1iCNwrD1sGoYD_OMQNMKM"


class TelegramBridgeTool(BaseTool):
    name = "telegram"
    description = "Send messages to Telegram chats or get recent messages. Args: 'send <chat_id> <text>' or 'get <chat_id> <limit>'"
    args_description = "send <chat_id> <text> | get <chat_id> <limit>"
    
    def execute(self, args: str) -> ToolResult:
        try:
            parts = args.strip().split(maxsplit=2)
            
            if len(parts) < 2:
                return ToolResult(False, "Invalid args. Use: send <chat_id> <text> | get <chat_id> <limit>")
            
            action = parts[0].lower()
            
            if action == "send":
                if len(parts) < 3:
                    return ToolResult(False, "Missing text. Use: send <chat_id> <text>")
                
                chat_id = parts[1]
                text = parts[2]
                return self._send_message(chat_id, text)
            
            elif action == "get":
                chat_id = parts[1]
                limit = int(parts[2]) if len(parts) > 2 else 10
                return self._get_messages(chat_id, limit)
            
            else:
                return ToolResult(False, f"Unknown action '{action}'. Use: send or get")
        
        except Exception as e:
            logger.error(f"Telegram tool error: {e}")
            return ToolResult(False, f"Telegram error: {e}")
    
    def _send_message(self, chat_id: str, text: str) -> ToolResult:
        """Send a message to a Telegram chat"""
        try:
            headers = {
                "Authorization": f"Bearer {BEARER_TOKEN}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "chat_id": int(chat_id) if chat_id.lstrip('-').isdigit() else chat_id,
                "text": text
            }
            
            response = requests.post(
                f"{BRIDGE_URL}/send",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return ToolResult(True, f"Message sent: {result.get('message_id', 'OK')}")
            else:
                return ToolResult(False, f"Send failed: {response.status_code} - {response.text[:200]}")
        
        except Exception as e:
            return ToolResult(False, f"Send error: {e}")
    
    def _get_messages(self, chat_id: str, limit: int = 10) -> ToolResult:
        """Get recent messages from a Telegram chat"""
        try:
            headers = {
                "Authorization": f"Bearer {BEARER_TOKEN}"
            }
            
            params = {
                "chat_id": int(chat_id) if chat_id.lstrip('-').isdigit() else chat_id,
                "limit": min(limit, 50)  # Cap at 50
            }
            
            response = requests.get(
                f"{BRIDGE_URL}/messages",
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                messages = response.json()
                
                if not messages:
                    return ToolResult(True, "No messages found")
                
                # Format messages
                lines = []
                for msg in messages[:limit]:
                    sender = msg.get('sender_id', 'unknown')
                    text = msg.get('text', '')[:100]
                    lines.append(f"[{sender}] {text}")
                
                return ToolResult(True, "\n".join(lines))
            else:
                return ToolResult(False, f"Get failed: {response.status_code} - {response.text[:200]}")
        
        except Exception as e:
            return ToolResult(False, f"Get error: {e}")
