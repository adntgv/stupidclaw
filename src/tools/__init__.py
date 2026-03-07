# src/tools/__init__.py
from src.tools.calculator import CalculatorTool
from src.tools.clock import ClockTool
from src.tools.web_search import WebSearchTool
from src.tools.web_fetch import WebFetchTool
from src.tools.file_ops import FileReadTool, FileWriteTool, FileListTool
from src.tools.shell import ShellTool
from src.tools.http_client import HTTPClientTool
from src.tools.docker_tool import DockerTool
from src.tools.telegram_bridge import TelegramBridgeTool
from src.tools.git_tool import GitTool

def get_default_tools() -> dict:
    tools = {}
    for cls in [CalculatorTool, ClockTool, WebSearchTool, WebFetchTool,
               FileReadTool, FileWriteTool, FileListTool, ShellTool,
               HTTPClientTool, DockerTool, TelegramBridgeTool, GitTool]:
        t = cls()
        tools[t.name] = t
    return tools
