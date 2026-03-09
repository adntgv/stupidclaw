# StupidClaw Refactor: From Defensive Code to LLM Reasoning

## Philosophy Change

**Before:** Hardcode every possible failure case  
**After:** Let the LLM see errors and reason about them

## Key Changes

### 1. Strong System Prompt
- Teaches the LLM how to handle errors
- Explains retry behavior
- Emphasizes reasoning and explanation
- More tokens (2048) for thinking through problems

### 2. Error Feedback Loop
- Tool errors returned as tool messages (not caught)
- LLM sees "TOOL ERROR: ..." and decides next steps
- Even API failures sent back as system messages
- No silent failures - everything is visible

### 3. Removed Defensive Code
- No None checks everywhere
- No generic fallback messages
- No hardcoded error strings
- Trust the LLM to handle edge cases

### 4. Reasoning Loop
- Up to 5 rounds of tool calls
- LLM sees all results (success or failure)
- Final summarization round if needed
- Larger context windows (3000 chars for tool output)

## What Got Deleted

- 100+ lines of defensive checks
- Hardcoded error messages
- Silent failure handling
- Memory skipping for None content
- Retry escalation logic (easy→medium→hard)

## What Got Added

- Comprehensive system prompt teaching error handling
- Error visibility (all failures go back to LLM)
- Final summarization round
- Better logging

## Result

**Before:** "I couldn't do that" with no explanation  
**After:** "I tried X, got error Y, so I'm trying Z instead..."

90% prompt engineering, 10% code - the right ratio for agentic systems.
