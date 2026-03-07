from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class Step(BaseModel):
    id: int
    description: str
    tool: Literal["calculator", "search", "time", "none"]
    args: str = Field(description="Arguments for the tool (e.g. '2+2' or 'weather in Almaty')")

class Plan(BaseModel):
    goal: str = Field(description="Restated user goal")
    steps: List[Step]

class ToolOutput(BaseModel):
    step_id: int
    success: bool
    result: str

class FinalResponse(BaseModel):
    answer: str
    confidence: float
    reasoning: str
