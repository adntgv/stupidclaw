# StupidClaw

AI assistant agent with 10 tools, 4-tier memory, cascade routing, and self-healing. Docker-ready.

## Quick Start

```bash
docker-compose up -d
# Bot: @adntgv_stupidclaw_bot
```

## Configuration

Edit `.env`:

```env
TELEGRAM_TOKEN=your_bot_token
OPENAI_API_KEY=any-key-works
OPENAI_BASE_URL=http://maxclaw:9999/v1  # Or your Mac's local IP: http://192.168.1.x:9999/v1
MODEL_NAME=MiniMax-M2.5
```

### Model Options

- **MiniMax-M2.5** (recommended): Set `OPENAI_BASE_URL=http://maxclaw:9999/v1` on your Mac, then point container to your Mac's local IP
- **Groq**: `OPENAI_BASE_URL=https://api.groq.com/openai/v1`, `MODEL_NAME=meta-llama/llama-4-scout-17b-16e-instruct`
- **OpenAI**: `OPENAI_BASE_URL=https://api.openai.com/v1`, `MODEL_NAME=gpt-4o`

## Features

- 10 built-in tools (web search, calculator, weather, etc.)
- 4-tier memory system (short-term, long-term, facts, skills)
- Cascade routing (easy/medium/hard)
- Self-healing and self-modification
- Docker-ready deployment

## License

MIT
