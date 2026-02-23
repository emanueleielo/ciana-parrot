<p align="center">
  <a href="https://cianaparrot.dev">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="images/parrot-logo.svg">
      <source media="(prefers-color-scheme: light)" srcset="images/parrot-logo-light.svg">
      <img src="images/parrot-logo.svg" alt="CianaParrot" width="460">
    </picture>
  </a>
</p>

<p align="center">
  <strong>Self-hosted AI assistant with multi-channel support, scheduled tasks, and extensible skills.</strong>
</p>

<p align="center">
  <a href="https://cianaparrot.dev"><img src="https://img.shields.io/badge/website-cianaparrot.dev-00F0FF?style=flat&logo=vercel&logoColor=white" alt="Website"></a>
  <img src="https://img.shields.io/badge/python-3.13+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/framework-DeepAgents-orange" alt="DeepAgents">
  <img src="https://img.shields.io/badge/deploy-Docker-2496ED?logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
</p>

---

## What is CianaParrot?

CianaParrot is a self-hosted AI personal assistant that runs on your own infrastructure — sandboxed inside Docker, but connected to your OS through secure bridges. Built on the [DeepAgents](https://github.com/deepagents/deepagents) framework with LangChain/LangGraph, it combines interactive chat via Telegram (and other channels) with autonomous scheduled tasks — all configured through a single YAML file.

**Key features:**
- **Multi-provider LLM** — Anthropic, OpenAI, Google Gemini, Groq, Ollama, OpenRouter, vLLM
- **Multi-channel** — Pluggable architecture, Telegram out of the box
- **Host gateway system** — Sandboxed in Docker, connected to your OS via a secure gateway. Each bridge exposes only allowed CLI commands — Spotify, Reminders, iMessage, Things, Bear Notes, Obsidian, 1Password, HomeKit, and more
- **Scheduled tasks** — Cron, interval, and one-shot tasks
- **Web tools** — Search (Brave / DuckDuckGo) and URL fetching built in
- **Skills system** — Add a folder in `skills/` with a `SKILL.md` and a `skill.py`, and it auto-registers
- **MCP support** — Connect external MCP servers for unlimited extensibility
- **Persistent memory** — Markdown-based identity and memory the agent updates itself
- **Observability** — Optional LangSmith tracing for debugging and monitoring
- **Docker-only deploy** — One command to build, one to run

## Architecture

<p align="center">
  <img src="images/architecture.svg" alt="CianaParrot Architecture" width="800">
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
├── Makefile                 # build, up, down, logs, restart, shell, test
├── src/
│   ├── main.py              # Entry point, event loop, wiring
│   ├── agent.py             # DeepAgents setup, tools, memory
│   ├── agent_response.py    # Response extraction from LangGraph messages
│   ├── config.py            # YAML loader with ${ENV_VAR} expansion
│   ├── events.py            # Shared event types (tool calls, thinking, text)
│   ├── middleware.py         # Skill filtering (env vars, bridge requirements)
│   ├── router.py            # Trigger detection, auth, thread mapping
│   ├── scheduler.py         # Cron/interval/once task runner
│   ├── store.py             # JSON file-backed key-value store
│   ├── utils.py             # Text truncation utilities
│   ├── channels/
│   │   ├── base.py          # AbstractChannel interface
│   │   └── telegram/
│   │       ├── channel.py   # Telegram adapter + mode handler system
│   │       ├── formatting.py# Markdown → Telegram HTML conversion
│   │       ├── rendering.py # Tool display, sub-agent collapsing, icons
│   │       ├── utils.py     # Typing indicator
│   │       └── handlers/
│   │           └── claude_code.py  # Claude Code mode handler
│   ├── gateway/
│   │   ├── server.py        # Host-side HTTP gateway server (runs on host)
│   │   ├── client.py        # Gateway HTTP client (used by agent inside Docker)
│   │   └── bridges/
│   │       └── claude_code/
│   │           └── bridge.py# CC session management, CLI execution, NDJSON parsing
│   └── tools/
│       ├── web.py           # Web search + URL fetch
│       ├── cron.py          # Schedule/list/cancel tasks
│       └── host.py          # host_execute tool (gateway bridge commands)
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

Everything lives in `config.yaml`. Secrets are referenced as `${ENV_VAR}` and expanded from `.env` at runtime. Config is validated at startup using Pydantic v2 models.

### LLM Provider

Change provider by editing two lines:

```yaml
provider:
  name: "anthropic"              # anthropic | openai | google-genai | groq | ollama
  model: "claude-sonnet-4-6"     # any model the provider supports
  api_key: "${ANTHROPIC_API_KEY}"
```

<details>
<summary><strong>All supported providers</strong></summary>

| Provider | `name` | Example `model` | Env var |
|---|---|---|---|
| Anthropic | `anthropic` | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
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

<details>
<summary><strong>Additional provider options</strong></summary>

```yaml
provider:
  temperature: 0         # 0.0–2.0
  max_tokens: 8192       # Max tokens per response
```

</details>

### Agent

```yaml
agent:
  workspace: "./workspace"       # Root directory for agent files
  max_tool_iterations: 20        # Max tool calls per turn (default: 20)
```

### Channels

```yaml
channels:
  telegram:
    enabled: true
    token: "${TELEGRAM_BOT_TOKEN}"
    trigger: "@Ciana"        # Required prefix in group chats (ignored in DMs)
    allowed_users: []        # Empty = everyone allowed
```

### Web Tools

```yaml
web:
  brave_api_key: "${BRAVE_API_KEY}"  # Optional, falls back to DuckDuckGo
  fetch_timeout: 30                  # URL fetch timeout in seconds
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
  poll_interval: 60              # Seconds between task checks
  data_file: "./data/scheduled_tasks.json"
```

### Logging

```yaml
logging:
  level: "INFO"                  # DEBUG | INFO | WARNING | ERROR
```

## Host Gateway System

CianaParrot runs inside a Docker container — it can't see your filesystem, can't launch your apps, can't touch your OS. That's the point. The agent is sandboxed by default.

The **gateway** is a lightweight HTTP server that runs on the host and connects the sandboxed agent to specific host capabilities. Each **bridge** is a named connector that exposes only the CLI commands you explicitly allow — nothing more.

```
Docker Container (sandboxed)              Host (macOS/Linux)
┌─────────────────────────────┐    ┌─────────────────────────────────┐
│  CianaParrot Agent          │    │  Host Gateway (port 9842)       │
│                             │    │  ┌───────────────────────────┐  │
│  host_execute(bridge, cmd)──│───►│  │ claude-code  → claude     │  │
│                             │    │  │ spotify      → spogo      │  │
│  Can't see the host OS      │    │  │ apple-reminders → remindctl│  │
│  Can't escape the sandbox   │    │  │ imessage     → imsg       │  │
│                             │    │  │ whatsapp     → wacli      │  │
│                             │    │  │ ... 14 bridges total       │  │
│                             │    │  └───────────────────────────┘  │
└─────────────────────────────┘    └─────────────────────────────────┘
```

A prompt injection against CianaParrot can't compromise your entire system — only the specific CLI commands allowed by the active bridge's allowlist.

### Available bridges

| Bridge | CLI | Description |
|--------|-----|-------------|
| `claude-code` | `claude` | Claude Code sessions (Telegram `/cc` mode) |
| `spotify` | `spogo` | Playback control and queue management |
| `apple-reminders` | `remindctl` | Manage Apple Reminders lists and items |
| `things` | `things` | Things 3 task management |
| `imessage` | `imsg` | Send and read iMessages |
| `whatsapp` | `wacli` | WhatsApp messaging |
| `bear-notes` | `grizzly` | Bear notes app |
| `obsidian` | `obsidian-cli` | Read and write to your Obsidian vault |
| `sonos` | `sonos` | Sonos speaker control |
| `openhue` | `openhue` | Philips Hue smart lights |
| `camsnap` | `camsnap` | Camera snapshots |
| `peekaboo` | `peekaboo` | Screen capture |
| `blucli` | `blu` | Bluetooth device control |
| `1password` | `op` | Look up credentials (read-only) |

### How it works

The agent calls `host_execute(bridge="spotify", command="spogo status")` which sends an HTTP request to the gateway on the host. The gateway validates the command against the bridge's allowlist, executes it, and returns `{stdout, stderr, returncode}`.

For Claude Code, a dedicated Telegram mode (`/cc`) provides interactive sessions with project/conversation selection, streaming output, and tool-call rendering.

Skills declare `requires_bridge: "spotify"` in their YAML frontmatter — skills are automatically hidden when their required bridge isn't configured.

### Setup

1. **Add a gateway token** to `.env`:
   ```
   GATEWAY_TOKEN=any-secret-string-you-choose
   ```

2. **Configure bridges** in `config.yaml`:
   ```yaml
   gateway:
     enabled: true
     url: "http://host.docker.internal:9842"
     token: "${GATEWAY_TOKEN}"
     port: 9842
     bridges:
       spotify:
         allowed_commands: ["spogo"]
       apple-reminders:
         allowed_commands: ["remindctl"]
   ```

3. **Install the CLI tools** on the host (e.g., `brew install steipete/tap/spogo`)

4. **Start the gateway** on the host:
   ```bash
   make gateway
   ```

5. **Restart the bot**:
   ```bash
   make restart
   ```

### Claude Code mode

| Command | Description |
|---------|-------------|
| `/cc` | Enter Claude Code mode — shows project list |
| `/cc exit` | Exit Claude Code mode |

Once in CC mode:
- **Select a project** from the paginated inline keyboard
- **Pick a conversation** to resume, or start a new one
- **Send messages** directly — they go to Claude Code instead of the main agent
- **Tool details** button expands to show each tool call with its output

### Adding a new bridge

1. Install the CLI tool on the host
2. Add a bridge entry in `config.yaml` under `gateway.bridges` with the CLI command in `allowed_commands`
3. Create a skill in `skills/your-bridge/SKILL.md` with `requires_bridge: "your-bridge"` in the frontmatter
4. Restart the bot — the skill auto-registers and the gateway allows the command

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
| `/help` | List all commands |
| `/new` | Reset conversation session |
| `/status` | System status |
| `/cc` | Enter Claude Code mode |
| `/cc exit` | Exit Claude Code mode |

## Observability

CianaParrot supports [LangSmith](https://smith.langchain.com/) for tracing and debugging agent execution. Add these to your `.env`:

```
LANGSMITH_API_KEY=lsv2_pt_...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=ciana-parrot
```

All agent invocations (tool calls, LLM requests, memory operations) will appear as traces in LangSmith Studio.

## Makefile

```
make build      # Build Docker image
make up         # Start in background
make down       # Stop
make logs       # Follow logs
make restart    # Rebuild and restart
make shell      # Shell into container
make test       # Run test suite (pytest)
make gateway    # Start host gateway on port 9842
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

1. Create `src/channels/myservice/` as a package
2. Implement the `AbstractChannel` interface (`start`, `stop`, `send`, `send_file`, `on_message`)
3. Add config section in `config.yaml` and a Pydantic model in `src/config.py`
4. Wire it up in `src/main.py`

## License

MIT
