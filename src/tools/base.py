# src/tools/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ToolResult:
    success: bool
    output: str

class BaseTool(ABC):
    name: str = ""
    description: str = ""
    args_description: str = ""

    @abstractmethod
    def execute(self, args: str) -> ToolResult:
        ...

    def schema(self) -> str:
        return f"{self.name}: {self.description} | args: {self.args_description}"
