# src/tools/web_fetch.py
import requests
import urllib3
from readability import Document
from bs4 import BeautifulSoup
from src.tools.base import BaseTool, ToolResult

# Disable SSL warnings for Docker environments
urllib3.disable_warnings()

class WebFetchTool(BaseTool):
    name = "web_fetch"
    description = "Fetch a URL and extract readable text content. Max 4000 chars."
    args_description = "URL to fetch"

    def execute(self, args: str) -> ToolResult:
        try:
            url = args.strip()
            resp = requests.get(
                url, 
                timeout=10, 
                verify=False,  # Fix SSL errors in Docker
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; StupidClaw/1.0)"
                }
            )
            resp.raise_for_status()
            doc = Document(resp.text)
            soup = BeautifulSoup(doc.summary(), "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            return ToolResult(True, text[:4000])
        except Exception as e:
            return ToolResult(False, f"Fetch error: {e}")
