<p align="center">
  <img src="images/img.png" alt="CianaParrot" width="400">
</p>

<p align="center">
  <strong>Self-hosted AI assistant with multi-channel support, scheduled tasks, and extensible skills.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.13+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/framework-DeepAgents-orange" alt="DeepAgents">
  <img src="https://img.shields.io/badge/deploy-Docker-2496ED?logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
</p>

---

## What is CianaParrot?

CianaParrot is a minimal but complete AI personal assistant that runs on your own infrastructure. It combines interactive chat via Telegram (and other channels) with autonomous scheduled tasks — all configured through a single YAML file.

**Key features:**
- **Multi-provider LLM** — Anthropic, OpenAI, Google Gemini, Groq, Ollama, OpenRouter, vLLM
- **Multi-channel** — Pluggable architecture, Telegram out of the box
- **Scheduled tasks** — Cron, interval, and one-shot tasks
- **Web tools** — Search (Brave / DuckDuckGo) and URL fetching built in
- **Skills system** — Add a folder in `skills/` with a `SKILL.md` and a `skill.py`, and it auto-registers
- **MCP support** — Connect external MCP servers for unlimited extensibility
- **Persistent memory** — Markdown-based identity and memory the agent updates itself
- **Docker-only deploy** — One command to build, one to run

## Architecture

<p align="center">
  <img src="images/architecture.png" alt="CianaParrot Architecture" width="700">
</p>

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/your-user/ciana-parrot.git
cd ciana-parrot
cp .env.example .env
```

Edit `.env` with your keys:

```
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
```

> **Telegram bot token:** Message [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`, and follow the prompts.

### 2. Build and run

```bash
make build
make up
```

### 3. Chat

Open your bot on Telegram, send `/start`, and start chatting.

## Project Structure

```
cianaparrot/
├── config.yaml              # Single config file
├── .env                     # Secrets (API keys, tokens)
├── Dockerfile
├── docker-compose.yml
├── Makefile                 # build, up, down, logs, restart, shell
├── src/
│   ├── main.py              # Entry point, event loop, wiring
│   ├── agent.py             # DeepAgents setup, middleware, tools
│   ├── config.py            # YAML loader with ${ENV_VAR} expansion
│   ├── router.py            # Trigger detection, auth, thread mapping
│   ├── scheduler.py         # Cron/interval/once task runner
│   ├── channels/
│   │   ├── base.py          # AbstractChannel interface
│   │   └── telegram.py      # Telegram adapter
│   └── tools/
│       ├── web.py           # Web search + URL fetch
│       └── cron.py          # Schedule/list/cancel tasks
├── workspace/
│   ├── IDENTITY.md          # Agent persona (name, tone, style)
│   ├── AGENT.md             # Behavioral instructions
│   ├── MEMORY.md            # Persistent memory (agent-updated)
│   └── sessions/            # JSONL conversation logs
├── skills/                  # Drop-in skill modules
└── data/
    ├── scheduled_tasks.json # Persisted scheduled tasks
    └── allowed_users.json   # Per-channel user allowlist
```

## Configuration

Everything lives in `config.yaml`. Secrets are referenced as `${ENV_VAR}` and expanded from `.env` at runtime.

### LLM Provider

Change provider by editing two lines:

```yaml
provider:
  name: "anthropic"                    # anthropic | openai | google-genai | groq | ollama
  model: "claude-sonnet-4-5-20250929"  # any model the provider supports
  api_key: "${ANTHROPIC_API_KEY}"
```

<details>
<summary><strong>All supported providers</strong></summary>

| Provider | `name` | Example `model` | Env var |
|---|---|---|---|
| Anthropic | `anthropic` | `claude-sonnet-4-5-20250929` | `ANTHROPIC_API_KEY` |
| OpenAI | `openai` | `gpt-4o` | `OPENAI_API_KEY` |
| Google Gemini | `google-genai` | `gemini-2.0-flash` | `GOOGLE_API_KEY` |
| Groq | `groq` | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| Ollama (local) | `ollama` | `llama3` | — |
| OpenRouter | `openai` | `anthropic/claude-sonnet-4-5` | `OPENROUTER_API_KEY` |
| vLLM | `openai` | `your-model` | — |

For OpenRouter, Ollama, and vLLM add `base_url`:

```yaml
provider:
  name: "openai"
  model: "anthropic/claude-sonnet-4-5"
  api_key: "${OPENROUTER_API_KEY}"
  base_url: "https://openrouter.ai/api/v1"
```

</details>

### Channels

```yaml
channels:
  telegram:
    enabled: true
    token: "${TELEGRAM_BOT_TOKEN}"
    trigger: "@Ciana"        # Required prefix in group chats (ignored in DMs)
    allowed_users: []        # Empty = everyone allowed
```

### MCP Servers

Connect external tools via [Model Context Protocol](https://modelcontextprotocol.io):

```yaml
mcp_servers:
  filesystem:
    transport: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]

  custom_api:
    transport: "sse"
    url: "http://localhost:8080/sse"
```

### Scheduled Tasks

The agent can create scheduled tasks via chat (e.g., "remind me every Monday at 9am to check reports"). Tasks are persisted in `data/scheduled_tasks.json`.

```yaml
scheduler:
  enabled: true
  poll_interval: 60
```

## Skills

Add capabilities by dropping a folder in `skills/`:

```
skills/
└── weather/
    ├── SKILL.md    # Description + instructions for the agent
    └── skill.py    # Python functions auto-registered as tools
```

```python
# skills/example/skill.py

def hello(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"
```

Functions with docstrings are auto-registered as agent tools by DeepAgents.

## User Access Control

Edit `data/allowed_users.json` to restrict who can use the bot:

```json
{
  "telegram": ["123456789", "987654321"]
}
```

Empty list = everyone allowed. Find your Telegram user ID via [@userinfobot](https://t.me/userinfobot).

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | List commands |
| `/new` | Reset session |
| `/status` | System status |

## Makefile

```
make build     # Build Docker image
make up        # Start in background
make down      # Stop
make logs      # Follow logs
make restart   # Restart
make shell     # Shell into container
make bridge-cc # Start Claude Code bridge on host (port 9842)
```

## Host Filesystem Access

The agent runs inside Docker and is sandboxed to the `workspace/` directory. To let it read or write files on your host machine, mount host directories as subdirectories of `workspace/` in `docker-compose.yml`:

```yaml
volumes:
  - ./workspace:/app/workspace
  - /path/to/your/folder:/app/workspace/host/folder-name
```

The agent can then access the files using its built-in tools (`ls`, `read_file`, `write_file`, etc.) at `host/folder-name/`.

### Read-only access

Append `:ro` to the volume mount to prevent the agent from modifying files:

```yaml
- ~/Documents:/app/workspace/host/documents:ro
```

### Read-write access

Omit the `:ro` suffix to allow the agent to create and edit files:

```yaml
- ~/Projects:/app/workspace/host/projects
```

### Example

```yaml
services:
  cianaparrot:
    volumes:
      - ./workspace:/app/workspace
      - ./data:/app/data
      - ./skills:/app/skills
      - ./config.yaml:/app/config.yaml:ro
      - ~/Documents:/app/workspace/host/documents:ro
      - ~/Projects:/app/workspace/host/projects
      - ~/Notes:/app/workspace/host/notes
```

After editing `docker-compose.yml`, restart with `make restart` (or `make build && make up` if you also changed the image).

## Customizing the Agent

The agent's behavior is fully controlled by three markdown files in `workspace/`:

| File | Purpose |
|------|---------|
| `IDENTITY.md` | Who the agent is — name, language, tone, personality |
| `AGENT.md` | How the agent behaves — tool usage rules, formatting guidelines |
| `MEMORY.md` | What the agent remembers — updated automatically across sessions |

Edit these files and restart. No code changes needed.

## Adding a New Channel

1. Create `src/channels/myservice.py`
2. Implement the `AbstractChannel` interface (`start`, `stop`, `send`, `send_file`, `on_message`)
3. Add config section in `config.yaml`
4. Wire it up in `src/main.py`

## License

MIT
