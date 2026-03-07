# src/tools/calculator.py
import math
from src.tools.base import BaseTool, ToolResult

class CalculatorTool(BaseTool):
    name = "calculator"
    description = "Evaluate a math expression. Supports all math module functions."
    args_description = "math expression (e.g. 'sqrt(144) + 3**2')"

    def execute(self, args: str) -> ToolResult:
        try:
            ns = {k: getattr(math, k) for k in dir(math) if not k.startswith('_')}
            ns.update({"abs": abs, "round": round, "min": min, "max": max})
            return ToolResult(True, str(eval(str(args), {"__builtins__": {}}, ns)))
        except Exception as e:
            return ToolResult(False, f"Calc error: {e}")
