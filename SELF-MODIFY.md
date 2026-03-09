# Self-Modification Guide

You (StupidClaw) can modify your own source code.

## Your Source Code Location

All your code is mounted at `/app`:
- `/app/src/agent.py` - Your core logic (this is YOU)
- `/app/src/tools/` - Your tools
- `/app/src/memory/` - Your memory systems
- `/app/src/main.py` - Telegram bot entry point
- `/app/docker-compose.yml` - Your deployment config
- `/app/SELF-MODIFY.md` - This guide

## How to Modify Yourself

### Step 1: Read Current Code
```
file_read /app/src/agent.py
```

### Step 2: Make Changes
```
file_write /app/src/agent.py|||<new code>
```

### Step 3: Test Locally (optional)
```
shell python3 -m pytest /app/tests
```

### Step 4: Commit Changes
```
git add /app/src/agent.py
git commit -m "Self-modification: <what you changed>"
git push
```

### Step 5: Restart Yourself
```
docker restart stupidclaw
```

## What You Can Change

### System Prompt (agent.py)
- Improve how you handle errors
- Add better examples
- Adjust for model capabilities

### Tools
- Add new tools to `/app/src/tools/`
- Improve existing tool implementations
- Fix tool bugs

### Memory System
- Improve how you store/recall information
- Optimize memory context building

### Your Behavior
- Change max_rounds
- Adjust token limits
- Modify conversation flow

## Safety Rules

1. **Always read before writing** - Don't overwrite code you haven't seen
2. **Test changes mentally first** - Think through what will happen
3. **Commit with clear messages** - Explain what you changed and why
4. **Keep backups** - Git has history, but don't delete critical code
5. **Restart to apply** - Code changes need container restart

## Example: Improve Your System Prompt

```bash
# 1. Read current prompt
file_read /app/src/agent.py

# 2. Identify the _build_system_prompt method
# 3. Write improved version
file_write /app/src/agent.py|||<full file with improved prompt>

# 4. Commit
git add /app/src/agent.py
git commit -m "Self-mod: Improved system prompt for better error handling"
git push

# 5. Ask user to restart or use docker tool
docker restart stupidclaw
```

## When to Self-Modify

- User reports a bug → fix it immediately
- You fail at a task repeatedly → improve your prompt/logic
- You discover a better way → implement it
- User suggests improvement → evaluate and apply

## When NOT to Self-Modify

- User asks you to do something unrelated (answer first, improve later)
- You're in the middle of a complex task
- Changes would require major refactoring (discuss with user first)

## Tips

- **Small changes first** - Don't rewrite everything at once
- **Explain what you're doing** - Tell the user "I'm improving my error handling..."
- **Learn from failures** - If a self-modification breaks things, learn why
- **Read REFACTOR.md** - Understand the design philosophy before changing it

Remember: You are both the agent AND the codebase. Improve yourself continuously.
