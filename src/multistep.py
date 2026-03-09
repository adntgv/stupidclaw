"""
Multi-Step Reasoning via Conversational Pipeline
Uses multiple LLM calls to simulate planning with weak models (Groq free tier)
"""
import json
import re
import logging
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Step:
    """Represents a single step in the execution plan"""
    number: int
    tool: str
    description: str
    params: Optional[Dict] = None  # Refined parameters
    result: Optional[str] = None   # Execution output
    status: str = "pending"  # pending|success|failed|skipped
    
    def __repr__(self):
        return f"Step({self.number}: {self.tool} - {self.status})"


@dataclass
class ExecutionState:
    """Tracks execution progress"""
    task: str
    steps: List[Step] = field(default_factory=list)
    current_step: int = 0
    llm_calls: int = 0
    failed_count: int = 0
    
    def next_step(self) -> Optional[Step]:
        """Get next pending step"""
        while self.current_step < len(self.steps):
            step = self.steps[self.current_step]
            if step.status == "pending":
                return step
            self.current_step += 1
        return None
    
    def mark_success(self, step: Step, result: str):
        """Mark step as successful"""
        step.status = "success"
        step.result = result
        self.current_step += 1
        logger.info(f"✅ {step} succeeded")
    
    def mark_failed(self, step: Step, error: str):
        """Mark step as failed"""
        step.status = "failed"
        step.result = error
        self.failed_count += 1
        logger.warning(f"❌ {step} failed: {error[:100]}")
    
    def get_completed_summary(self) -> str:
        """Get summary of completed steps for LLM context"""
        completed = [s for s in self.steps if s.status == "success"]
        if not completed:
            return "No steps completed yet."
        
        lines = []
        for step in completed:
            result_preview = step.result[:80] if step.result else "No output"
            lines.append(f"Step {step.number} ({step.tool}): {result_preview}...")
        
        return "\n".join(lines)


class PipelinedPlanner:
    """Uses multiple FREE LLM calls to simulate planning"""
    
    def __init__(self, llm_func: Callable):
        """
        Args:
            llm_func: Function that takes (prompt, max_tokens) and returns string
        """
        self.llm = llm_func
        self.conversation = []  # Track all LLM interactions
    
    def plan_task(self, task: str, tools: List[str]) -> List[Step]:
        """
        Phase 1: Ask LLM to break down the task into steps
        
        Returns:
            List of Step objects with tool and description
        """
        tools_list = ", ".join(tools)
        
        planning_prompt = f"""Task: {task}

You have these tools available:
{tools_list}

Break this task into 3-7 specific steps.

For each step write EXACTLY:
Step N: [tool_name] - description

Example:
Step 1: file_read - read the current agent.py file
Step 2: file_write - write the fixed version
Step 3: git - add the changed file

Be specific. ONLY list steps, nothing else."""
        
        logger.info(f"Planning task: {task}")
        plan_text = self.llm(planning_prompt, max_tokens=300)
        self.conversation.append(("planning", plan_text))
        
        steps = self._parse_plan(plan_text)
        logger.info(f"Generated {len(steps)} steps")
        
        return steps
    
    def refine_step(self, step: Step, prev_results: str) -> Dict:
        """
        Phase 2: Ask LLM for exact parameters for this step
        
        Returns:
            Dict of parameters for the tool
        """
        # Tool-specific schema hints
        schema_hints = {
            "file_read": '{"path": "/app/src/agent.py"}',
            "file_write": '{"path": "/app/src/agent.py", "content": "..."}',
            "git": '{"command": "add src/agent.py"}',
            "shell": '{"command": "python3 test.py"}',
            "web_search": '{"query": "latest AI news"}',
            "web_fetch": '{"url": "https://example.com"}'
        }
        
        example = schema_hints.get(step.tool, '{"args": "..."}')
        
        refine_prompt = f"""You are executing step {step.number}: {step.description}

Previous results:
{prev_results[:500]}

What are the EXACT parameters for the {step.tool} tool?

Output ONLY valid JSON. Example format:
{example}

NO explanations. ONLY JSON."""
        
        logger.info(f"Refining step {step.number} ({step.tool})")
        params_text = self.llm(refine_prompt, max_tokens=500)
        self.conversation.append((f"refine_step_{step.number}", params_text))
        
        params = self._parse_params(params_text, step.tool)
        return params
    
    def verify_step(self, step: Step, actual_result: str) -> Dict:
        """
        Phase 3: Ask LLM if step succeeded (only if programmatic check unclear)
        
        Returns:
            {"success": bool, "reason": str, "retry": bool, "suggestion": str}
        """
        verify_prompt = f"""Step {step.number} ({step.tool}) just executed.

Expected: {step.description}

Actual output:
{actual_result[:500]}

Did this step succeed?

Answer with ONE of these EXACT formats:
SUCCESS
or
FAILED: [reason] | RETRY: [what to change]
or
FAILED: [reason] | ABORT

Choose carefully."""
        
        logger.info(f"Verifying step {step.number}")
        analysis = self.llm(verify_prompt, max_tokens=150)
        self.conversation.append((f"verify_step_{step.number}", analysis))
        
        # Parse verification result
        if "SUCCESS" in analysis.upper():
            return {"success": True, "reason": analysis}
        elif "RETRY:" in analysis:
            parts = analysis.split("RETRY:")
            suggestion = parts[1].strip() if len(parts) > 1 else ""
            return {"success": False, "retry": True, "suggestion": suggestion}
        elif "ABORT" in analysis:
            return {"success": False, "retry": False, "abort": True}
        else:
            return {"success": False, "retry": False, "error": analysis}
    
    def replan_after_failure(self, state: ExecutionState, failed_step: Step) -> str:
        """
        Phase 4: Ask LLM how to handle failure
        
        Returns:
            String with replanning suggestion
        """
        replan_prompt = f"""Original task: {state.task}

Completed successfully:
{state.get_completed_summary()}

Step {failed_step.number} FAILED:
Tool: {failed_step.tool}
Expected: {failed_step.description}
Error: {failed_step.result[:300]}

What should we do?

Choose ONE:
1. SKIP: Continue to next step
2. RETRY: Try same step differently - [explain changes]
3. ABORT: Task impossible - [explain why]

Answer format:
[SKIP/RETRY/ABORT]: explanation"""
        
        logger.info(f"Replanning after step {failed_step.number} failure")
        new_plan = self.llm(replan_prompt, max_tokens=200)
        self.conversation.append((f"replan_step_{failed_step.number}", new_plan))
        
        return new_plan
    
    def _parse_plan(self, plan_text: str) -> List[Step]:
        """Parse LLM output into Step objects"""
        steps = []
        for line in plan_text.split('\n'):
            # Match "Step N: [tool] - description"
            match = re.match(r'Step\s+(\d+):\s*\[?(\w+)\]?\s*-\s*(.+)', line, re.IGNORECASE)
            if match:
                steps.append(Step(
                    number=int(match.group(1)),
                    tool=match.group(2).lower(),
                    description=match.group(3).strip()
                ))
        
        if not steps:
            logger.warning(f"Failed to parse plan from: {plan_text[:200]}")
        
        return steps
    
    def _parse_params(self, params_text: str, tool_name: str) -> Dict:
        """Parse parameters with robust error handling"""
        # Try direct JSON parse
        try:
            return json.loads(params_text)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown
        match = re.search(r'```(?:json)?\n(.*?)\n```', params_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        
        # Try to fix common issues
        try:
            # Replace single quotes with double quotes
            fixed = params_text.replace("'", '"')
            # Add quotes to unquoted keys (simple heuristic)
            fixed = re.sub(r'(\w+):', r'"\1":', fixed)
            return json.loads(fixed)
        except:
            pass
        
        # Last resort: extract key-value pairs heuristically
        logger.warning(f"Could not parse JSON, using heuristic extraction: {params_text[:100]}")
        return self._extract_params_heuristic(params_text, tool_name)
    
    def _extract_params_heuristic(self, text: str, tool_name: str) -> Dict:
        """Extract parameters when JSON parsing fails"""
        params = {}
        
        # Look for common patterns
        if tool_name == "file_read":
            # Extract path
            path_match = re.search(r'[\'"]?path[\'"]?\s*:\s*[\'"]([^\'"]+)[\'"]', text, re.IGNORECASE)
            if path_match:
                params["path"] = path_match.group(1)
        
        elif tool_name == "file_write":
            # Extract path and content
            path_match = re.search(r'[\'"]?path[\'"]?\s*:\s*[\'"]([^\'"]+)[\'"]', text, re.IGNORECASE)
            content_match = re.search(r'[\'"]?content[\'"]?\s*:\s*[\'"](.+?)[\'"]', text, re.IGNORECASE | re.DOTALL)
            
            if path_match:
                params["path"] = path_match.group(1)
            if content_match:
                params["content"] = content_match.group(1)
        
        elif tool_name in ("git", "shell"):
            # Extract command
            cmd_match = re.search(r'[\'"]?command[\'"]?\s*:\s*[\'"]([^\'"]+)[\'"]', text, re.IGNORECASE)
            if cmd_match:
                params["command"] = cmd_match.group(1)
        
        return params


class ConversationalExecutor:
    """Execute tasks through conversational pipeline with weak model"""
    
    MAX_RETRIES = 1
    MAX_TOTAL_FAILURES = 3
    
    def __init__(self, llm_func: Callable, tools: Dict):
        """
        Args:
            llm_func: Function (prompt, max_tokens) -> str
            tools: Dict of {tool_name: tool_object}
        """
        self.planner = PipelinedPlanner(llm_func)
        self.tools = tools
        self.llm = llm_func
    
    def execute(self, task: str) -> Dict:
        """
        Execute task through conversational planning
        
        Returns:
            {
                "success": bool,
                "completed_steps": int,
                "total_steps": int,
                "final_message": str,
                "llm_calls": int
            }
        """
        # Phase 1: Planning
        tool_names = list(self.tools.keys())
        steps = self.planner.plan_task(task, tool_names)
        
        if not steps:
            return {
                "success": False,
                "completed_steps": 0,
                "total_steps": 0,
                "final_message": "Failed to generate plan",
                "llm_calls": 1
            }
        
        state = ExecutionState(task=task, steps=steps)
        state.llm_calls = 1  # Planning call
        
        # Main execution loop
        while step := state.next_step():
            logger.info(f"\n=== Step {step.number}/{len(steps)}: {step.tool} - {step.description} ===")
            
            # Phase 2: Refine parameters
            prev_results = state.get_completed_summary()
            params = self.planner.refine_step(step, prev_results)
            step.params = params
            state.llm_calls += 1
            
            # Execute
            success = self._execute_and_verify(step, state)
            
            if not success:
                # Try once more if retry suggested
                logger.info(f"Retrying step {step.number}")
                success = self._execute_and_verify(step, state)
            
            if not success:
                # Handle failure
                if state.failed_count >= self.MAX_TOTAL_FAILURES:
                    return self._build_result(state, "Too many failures. Aborting.")
                
                # Ask LLM what to do
                replan = self.planner.replan_after_failure(state, step)
                state.llm_calls += 1
                
                if "ABORT" in replan.upper():
                    return self._build_result(state, f"Task aborted: {replan}")
                elif "SKIP" in replan.upper():
                    step.status = "skipped"
                    logger.info(f"Skipping step {step.number}")
                    continue
                else:
                    # Can't continue
                    return self._build_result(state, f"Failed at step {step.number}")
        
        # Success!
        return self._build_result(state, "All steps completed successfully", success=True)
    
    def _convert_params_to_args(self, tool_name: str, params: dict) -> str:
        """Convert dict parameters to string format expected by tools"""
        if isinstance(params, str):
            return params  # Already a string
        
        if tool_name == "file_read":
            return params.get("path") or params.get("filename") or params.get("file") or params.get("file_path", "")
        elif tool_name == "file_write":
            path = params.get("path") or params.get("filename") or params.get("file", "")
            content = params.get("content") or params.get("text") or params.get("data", "")
            return f"{path}|||{content}"
        elif tool_name == "file_list":
            return params.get("directory") or params.get("dir") or params.get("subdirectory") or params.get("folder") or params.get("path", "")
        elif tool_name == "web_search":
            return params.get("query") or params.get("q") or params.get("search") or params.get("term", "")
        elif tool_name == "web_fetch":
            return params.get("url") or params.get("link") or params.get("uri") or params.get("address", "")
        elif tool_name in ("shell", "git"):
            return params.get("command") or params.get("cmd") or params.get("script", "")
        else:
            return params.get("args", "") or next(iter(params.values()), "") if params else ""
    
    def _execute_and_verify(self, step: Step, state: ExecutionState) -> bool:
        """Execute step and verify result"""
        # Execute tool
        try:
            tool = self.tools.get(step.tool)
            if not tool:
                step.result = f"Tool '{step.tool}' not found"
                state.mark_failed(step, step.result)
                return False
            
            # Convert dict params to string format
            args_str = self._convert_params_to_args(step.tool, step.params)
            
            result = tool.execute(args_str)
            
            # Extract string output from ToolResult object
            result_str = result.output if hasattr(result, 'output') else str(result)
            
            # Programmatic verification first
            quick_check = self._quick_verify(step.tool, result_str)
            
            if quick_check is True:
                # Clear success, skip LLM call
                state.mark_success(step, result_str)
                return True
            
            elif quick_check is False:
                # Clear failure
                state.mark_failed(step, result_str)
                
                # Ask LLM to verify (maybe it's not actually a failure)
                verification = self.planner.verify_step(step, result_str)
                state.llm_calls += 1
                
                if verification["success"]:
                    # LLM says success despite programmatic failure
                    state.mark_success(step, result_str)
                    return True
                
                return False
            
            else:
                # Unclear, ask LLM
                verification = self.planner.verify_step(step, result_str)
                state.llm_calls += 1
                
                if verification["success"]:
                    state.mark_success(step, result_str)
                    return True
                else:
                    state.mark_failed(step, result_str)
                    return False
        
        except Exception as e:
            error = f"Exception: {str(e)}"
            logger.error(f"Step {step.number} exception: {e}")
            state.mark_failed(step, error)
            return False
    
    def _quick_verify(self, tool_name: str, result: str) -> Optional[bool]:
        """
        Programmatic verification (no LLM)
        
        Returns:
            True: Clear success, skip LLM
            False: Clear failure, use LLM to confirm
            None: Unclear, must use LLM
        """
        result_lower = result.lower()
        
        # Git operations
        if tool_name == "git":
            if "error" in result_lower or "fatal" in result_lower:
                return False
            if len(result) < 500:  # Short output usually means success
                return True
            return None
        
        # File operations
        if tool_name == "file_write":
            if "error" in result_lower:
                return False
            # Check if file exists (would need access to filesystem)
            # For now, trust the tool
            return True if len(result) < 100 else None
        
        if tool_name == "file_read":
            if "error" in result_lower or "not found" in result_lower:
                return False
            if len(result) > 10:  # Got some content
                return True
            return None
        
        # Shell commands
        if tool_name == "shell":
            if "error" in result_lower:
                return False
            # Look for success indicators
            if "success" in result_lower or "completed" in result_lower:
                return True
            return None
        
        # Web operations
        if tool_name in ("web_search", "web_fetch"):
            if "error" in result_lower or "failed" in result_lower:
                return False
            if len(result) > 50:
                return True
            return None
        
        # Default: unclear, use LLM
        return None
    
    def _build_result(self, state: ExecutionState, message: str, success: bool = None) -> Dict:
        """Build final result dict"""
        completed = sum(1 for s in state.steps if s.status == "success")
        
        if success is None:
            success = completed == len(state.steps)
        
        return {
            "success": success,
            "completed_steps": completed,
            "total_steps": len(state.steps),
            "final_message": message,
            "llm_calls": state.llm_calls,
            "conversation": self.planner.conversation
        }
