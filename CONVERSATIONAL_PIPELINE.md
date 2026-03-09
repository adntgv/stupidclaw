# Conversational Pipeline Architecture
## Multi-Step Reasoning with FREE Models Only

**Goal:** Enable complex multi-step tasks using only Groq free tier (Llama/Scout) through conversational pipeline.

---

## Core Principle

**Split complex reasoning into SIMPLE, FOCUSED questions.**

Instead of asking weak model to "plan and execute" (fails), we ask:
1. "What are the steps?" (planning)
2. "What params for step N?" (refinement)
3. "Did step N work?" (verification)
4. "Step failed, what now?" (replanning)

Each question is simple enough for weak models to answer correctly.

---

## Architecture

### Phase 1: PLANNING (1 LLM call)

**Prompt:**
```
Task: {user_task}

You have these tools available:
- file_read (read file)
- file_write (write file)
- git (run git command)
- shell (run shell command)
- web_search (search web)
- web_fetch (get URL content)

Break this task into 3-7 specific steps.

For each step write:
Step N: [tool_name] - description

Example:
Step 1: file_read - read the current agent.py file
Step 2: file_write - write the fixed version
Step 3: git - add the changed file
Step 4: git - commit with message
Step 5: git - push to remote

Be specific. ONLY list steps, nothing else.
```

**Parse response:** Extract step number, tool name, description using regex.

---

### Phase 2: REFINE (1 LLM call per step)

**Prompt:**
```
You are executing step {step_num} of {total_steps}.

Current step: {step_description}

Previous results:
{previous_step_outputs}

What are the EXACT parameters for the {tool_name} tool?

Output ONLY valid JSON with these exact keys:
{tool_specific_schema}

Example for file_write:
{"path": "/app/src/agent.py", "content": "import os\n..."}

Example for git:
{"command": "add src/agent.py"}

NO explanations. ONLY JSON.
```

**Parse response:** Extract JSON, validate against tool schema, provide defaults for missing fields.

**Fallback:** If JSON parsing fails, retry with: "Invalid JSON. Try again with proper format: {...}"

---

### Phase 3: EXECUTE (no LLM)

Run the tool with parsed parameters. Programmatic, not LLM-based.

---

### Phase 4: VERIFY (1 LLM call per step)

**Strategy: Hybrid (programmatic + LLM)**

**First: Programmatic check**
```python
def quick_verify(tool_name, result):
    """Fast programmatic checks"""
    if tool_name == "git":
        return "error" not in result.lower() and "fatal" not in result.lower()
    elif tool_name == "file_write":
        return "written" in result.lower() or len(result) < 100
    elif tool_name == "shell":
        return "error" not in result.lower()
    # Default: check if we got output
    return len(result) > 0
```

**If programmatic check PASSES:** Skip LLM, mark success, continue.

**If programmatic check FAILS:** Ask LLM to analyze:

```
Step {step_num} ({tool_name}) just executed.

Expected: {step_description}

Actual output:
{result[:500]}

Did this step succeed?

Answer with ONE of these EXACT formats:
SUCCESS
or
FAILED: [reason] | RETRY: [what to change]
or
FAILED: [reason] | ABORT: [task impossible]

Choose carefully. Be concise.
```

**Parse:** Check for SUCCESS/FAILED/RETRY/ABORT keywords.

---

### Phase 5: REPLAN (1 LLM call on failure)

**Only trigger if:**
- Step failed programmatic check
- LLM said "RETRY" or "ABORT"

**Prompt:**
```
Original task: {original_task}

Steps completed successfully:
{list_of_completed_steps_and_outputs}

Step {failed_step_num} FAILED:
Tool: {tool_name}
Expected: {step_description}
Error: {error_message}

What should we do?

Choose ONE:
1. SKIP: Continue to next step
2. RETRY: Try same step with different approach - [explain what to change]
3. ABORT: Task is impossible - [explain why]

Answer format:
[SKIP/RETRY/ABORT]: explanation
```

**Parse:** Extract action and reasoning.

---

## State Management

```python
@dataclass
class Step:
    number: int
    tool: str
    description: str
    params: dict = None  # Refined parameters
    result: str = None   # Execution output
    status: str = "pending"  # pending|success|failed|skipped
    
@dataclass
class ExecutionState:
    task: str
    steps: List[Step]
    current_step: int = 0
    llm_calls: int = 0  # Track for monitoring
    
    def next_step(self):
        while self.current_step < len(self.steps):
            step = self.steps[self.current_step]
            if step.status == "pending":
                return step
            self.current_step += 1
        return None
    
    def mark_success(self, step: Step, result: str):
        step.status = "success"
        step.result = result
        self.current_step += 1
    
    def mark_failed(self, step: Step, error: str):
        step.status = "failed"
        step.result = error
```

---

## Error Recovery Flow

```
Execute step N
    ↓
Programmatic check
    ↓
PASS? → Mark success → Next step
    ↓
FAIL? → LLM verify
    ↓
SUCCESS? → Mark success → Next step (LLM was wrong, ignore)
    ↓
RETRY? → Replan → Get new params → Execute again (max 1 retry)
    ↓
ABORT? → Stop execution → Return partial results
```

---

## Optimization: Skip Unnecessary LLM Calls

**When to SKIP verification LLM call:**

1. **File operations** - Check file exists:
   ```python
   if tool == "file_write":
       if Path(params["path"]).exists():
           return SUCCESS  # Skip LLM call
   ```

2. **Git operations** - Check error keywords:
   ```python
   if tool == "git":
       if "error" not in result.lower() and "fatal" not in result.lower():
           return SUCCESS  # Skip LLM call
   ```

3. **Simple reads** - If got data:
   ```python
   if tool == "file_read":
       if len(result) > 10:  # Got some content
           return SUCCESS  # Skip LLM call
   ```

**Result:** Reduces LLM calls from ~20 to ~10 for 5-step task.

---

## Edge Cases & Solutions

### 1. LLM gives invalid JSON

**Problem:** Weak models often output: `{"path": /app/file}` (missing quotes)

**Solution:**
```python
def parse_params_robust(text, tool_name):
    try:
        return json.loads(text)
    except:
        # Try to extract JSON from markdown
        match = re.search(r'```(?:json)?\n(.*?)\n```', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        
        # Try to fix common issues
        fixed = text.replace("'", '"')  # Single quotes
        fixed = re.sub(r'(\w+):', r'"\1":', fixed)  # Unquoted keys
        try:
            return json.loads(fixed)
        except:
            # Last resort: extract values manually
            return extract_params_heuristic(text, tool_name)
```

### 2. Circular dependencies

**Problem:** LLM might plan: Step 2 depends on Step 3, Step 3 depends on Step 2

**Solution:** Validate during planning parse:
```python
def validate_plan(steps):
    """Detect circular dependencies"""
    for i, step in enumerate(steps):
        # Steps can only depend on previous steps
        # (We don't explicitly track deps, just execute in order)
        pass
    return True
```

**Simpler:** Just execute steps in order. No explicit dependency tracking needed.

### 3. Infinite retry loops

**Problem:** Step fails → retry → fails → retry...

**Solution:**
```python
MAX_RETRIES = 1  # Only retry once per step
MAX_TOTAL_FAILURES = 3  # Abort if 3 steps fail

if state.failed_count >= MAX_TOTAL_FAILURES:
    return "Too many failures. Aborting task."
```

### 4. LLM doesn't follow format

**Problem:** Instead of "Step 1: file_read - description", outputs paragraph

**Solution:** Retry planning with stricter prompt:
```
You MUST use this EXACT format:
Step 1: [tool] - [description]
Step 2: [tool] - [description]

Do NOT write paragraphs. Do NOT explain. ONLY the step list.
```

If still fails after 1 retry, fall back to simple execution (skip planning).

---

## Implementation Checklist

- [ ] PipelinedPlanner class
  - [ ] plan_task() - initial planning
  - [ ] refine_step() - get params
  - [ ] verify_step() - check success
  - [ ] replan_after_failure() - adjust plan
- [ ] ExecutionState dataclass
- [ ] Step dataclass
- [ ] Programmatic verification functions
- [ ] JSON parsing with fallbacks
- [ ] Error recovery logic
- [ ] Main execution loop
- [ ] Logging/debugging

---

## Testing Strategy

**Test Case 1: Simple task (no failures)**
```
User: "Read agent.py and count the lines"
Expected:
  - Plan: 2 steps (file_read, no follow-up needed)
  - LLM calls: 1 (planning) + 1 (refine step 1) = 2
  - Result: Success
```

**Test Case 2: Multi-step with dependencies**
```
User: "Fix error handling in agent.py and commit it"
Expected:
  - Plan: file_read → file_write → git add → git commit → git push
  - LLM calls: ~7-10 (planning + refine each step, skip some verifies)
  - Result: All steps succeed
```

**Test Case 3: Failure recovery**
```
User: "Commit changes" (but no changes exist)
Expected:
  - Plan: git commit → git push
  - Step 1 fails (nothing to commit)
  - LLM verify detects failure
  - Replan: ABORT (no changes to commit)
  - Result: Graceful abort with explanation
```

**Test Case 4: Invalid JSON handling**
```
Simulate LLM returning: `{path: /app/file.txt}`
Expected:
  - Parser detects invalid JSON
  - Fixes to: `{"path": "/app/file.txt"}`
  - Execution continues
```

---

## Performance Targets

**For 5-step task:**
- Total LLM calls: 8-12 (planning + refines + selective verifies)
- Response time: < 30 seconds
- Success rate: > 80% for well-defined tasks
- Cost: $0.00 (Groq free tier)

**Optimization opportunities:**
- Cache plans for similar tasks
- Skip verification for low-risk steps
- Batch multiple refine calls if model supports it

---

## Future Enhancements

1. **Learning from failures:** Store failed plans + what worked in episodic memory
2. **Plan templates:** After seeing "fix code + commit" 10 times, suggest cached plan
3. **Parallel execution:** For independent steps (read file A + read file B)
4. **Better parsing:** Fine-tune weak model on planning format
5. **Self-improvement:** Bot can modify its own prompt templates

---

## Integration with Existing StupidClaw

**Changes needed in `src/agent.py`:**

1. Add imports:
   ```python
   from src.multistep import ConversationalPipeline
   ```

2. Detect complex tasks:
   ```python
   def run(self, user_message, chat_id):
       # Detect multi-step tasks
       if self._is_multistep_task(user_message):
           pipeline = ConversationalPipeline(self.client, self.tools)
           return pipeline.execute(user_message)
       else:
           # Existing single-step flow
           return self._run_with_tools(...)
   
   def _is_multistep_task(self, message):
       keywords = ["fix and commit", "read and write", "search and summarize", 
                   "analyze and improve", "debug and deploy"]
       return any(kw in message.lower() for kw in keywords) or len(message.split()) > 15
   ```

3. Keep existing code for simple tasks (backward compatible)

---

## Summary

**Architecture:** 4-phase conversational pipeline (plan → refine → execute → verify)

**Key insight:** Weak models can answer simple focused questions, just not complex multi-step planning.

**Optimization:** Programmatic verification skips most LLM verify calls.

**Error recovery:** Dynamic replanning on failures.

**Cost:** 100% free (Groq), ~10 LLM calls per 5-step task.

**Next step:** Implement `src/multistep.py` with this architecture.
