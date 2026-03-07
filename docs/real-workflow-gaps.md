# StupidClaw vs OpenClaw — Real Workflow Gap Analysis

## Workflows we actually use (from last 2-4 weeks)

### 1. Web Research + Summarize
- Search for topics, fetch URLs, extract readable content, synthesize
- OpenClaw: web_fetch + web_search tools, Perplexity skill
- StupidClaw: ✅ web_search (DuckDuckGo), ⚠️ web_fetch (SSL issues), needs fixing

### 2. Code Generation + Deployment
- Write code, create Dockerfiles, docker-compose, deploy to Coolify
- OpenClaw: coding-agent skill, exec tool, Coolify skill
- StupidClaw: ❌ No Coolify API, ❌ no code generation workflow, basic shell only

### 3. GitHub Operations
- Create repos, push code, manage PRs, check CI
- OpenClaw: GitHub skill + gh CLI
- StupidClaw: ❌ No GitHub integration

### 4. Telegram Messaging
- Send messages, files, reactions to Telegram chats/topics
- OpenClaw: message tool, Telegram bridge
- StupidClaw: ❌ Only receives via bot polling, can't send to other chats

### 5. Scheduled Tasks (Cron)
- Morning briefs, job search, digests, periodic checks
- OpenClaw: cron system, heartbeat loop
- StupidClaw: ⚠️ Has APScheduler skeleton, not functional

### 6. Memory Across Sessions
- Remember user prefs, project context, decisions
- OpenClaw: MEMORY.md + memory/*.md + memory_search
- StupidClaw: ⚠️ Has ChromaDB + hot memory, but ChromaDB slow and unreliable

### 7. Sub-Agent Spawning
- Delegate complex tasks to background workers
- OpenClaw: sessions_spawn with different models
- StupidClaw: ⚠️ Has basic decomposition, but no real parallelism

### 8. Browser Automation
- Control Chrome, scrape pages, fill forms
- OpenClaw: browser tool, nodriver, Playwright
- StupidClaw: ❌ No browser control

### 9. File Management + Project Scaffolding
- Create project structures, edit configs, manage files
- OpenClaw: read/write/edit tools
- StupidClaw: ✅ file_read, file_write, file_list (sandboxed)

### 10. Self-Improvement / Error Detection
- Detect failures, fix root causes, update own code
- OpenClaw: self-improvement skill, AGENTS.md updates
- StupidClaw: ❌ Logs errors but doesn't analyze or fix them

### 11. API Integrations
- Coolify, Trello, Plane, LemonSqueezy, Google Analytics
- OpenClaw: Direct API calls via exec/curl
- StupidClaw: ❌ No external API tools

### 12. Voice / TTS
- Convert text to speech, transcribe audio
- OpenClaw: tts tool, Whisper skill
- StupidClaw: ❌ No voice capability

## Priority for StupidClaw (by frequency of use)
1. **Self-healing** (detect + fix own errors) — HIGHEST
2. **Telegram bridge** (send to other chats, not just reply)
3. **Docker/deployment** (at least docker-compose up/restart)
4. **GitHub** (push code, create repos)
5. **Cron/scheduler** (periodic tasks)
6. **External APIs** (generic HTTP client tool)
7. **Browser** (later, complex)
8. **Voice** (later, nice-to-have)
