# src/tools/web_search.py
from src.tools.base import BaseTool, ToolResult

class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web via DuckDuckGo. Returns top 5 results with title, URL, snippet."
    args_description = "search query string"

    def execute(self, args: str) -> ToolResult:
        try:
            from duckduckgo_search import DDGS
            # Fix: model sometimes passes list or quoted string
            query = str(args).strip("[]'\"")
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=5):
                    results.append(f"[{r['title']}]({r['href']})\n{r['body']}")
            if not results:
                return ToolResult(True, "No results found.")
            return ToolResult(True, "\n\n".join(results))
        except Exception as e:
            return ToolResult(False, f"Search error: {e}")
