"""
Generic HTTP Client Tool — Make arbitrary HTTP requests
"""
import json
import requests
from src.tools.base import BaseTool, ToolResult

class HTTPClientTool(BaseTool):
    name = "http"
    description = "Make HTTP requests (GET, POST, PUT, DELETE) with custom headers and body"
    args_description = 'JSON string: {"method": "GET", "url": "https://...", "headers": {...}, "body": {...}}'
    
    def execute(self, args: str) -> ToolResult:
        try:
            # Parse JSON args
            if isinstance(args, str):
                params = json.loads(args)
            else:
                params = args
            
            method = params.get("method", "GET").upper()
            url = params.get("url")
            headers = params.get("headers", {})
            body = params.get("body", {})
            
            if not url:
                return ToolResult(False, "Missing 'url' in parameters")
            
            # Replace host.docker.internal with proper Linux networking
            if "host.docker.internal" in url:
                # On Linux, use gateway IP (172.17.0.1 for default bridge)
                # Or 10.0.0.1 as suggested in task
                url = url.replace("host.docker.internal", "10.0.0.1")
            
            # Make the request
            timeout = params.get("timeout", 10)
            
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=timeout)
            elif method == "POST":
                resp = requests.post(url, headers=headers, json=body, timeout=timeout)
            elif method == "PUT":
                resp = requests.put(url, headers=headers, json=body, timeout=timeout)
            elif method == "DELETE":
                resp = requests.delete(url, headers=headers, timeout=timeout)
            else:
                return ToolResult(False, f"Unsupported method: {method}")
            
            # Format response
            status = resp.status_code
            
            # Try to parse JSON response
            try:
                body_text = json.dumps(resp.json(), indent=2)
            except:
                body_text = resp.text
            
            # Truncate to 2000 chars
            output = f"Status: {status}\n\n{body_text[:2000]}"
            
            success = 200 <= status < 300
            return ToolResult(success, output)
            
        except json.JSONDecodeError as e:
            return ToolResult(False, f"Invalid JSON args: {e}")
        except requests.Timeout:
            return ToolResult(False, "Request timed out")
        except requests.RequestException as e:
            return ToolResult(False, f"HTTP error: {e}")
        except Exception as e:
            return ToolResult(False, f"Error: {e}")
