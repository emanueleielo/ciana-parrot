---
title: Configuration
---

# Configuration

CianaParrot is configured through a single `config.yaml` file at the project root. All secrets are referenced as `${ENV_VAR}` placeholders and expanded at runtime from the `.env` file. The entire configuration is validated at startup using Pydantic v2 models -- invalid values produce clear error messages before the bot starts.

!!! warning "Secrets belong in `.env`"
    Never put API keys or tokens directly in `config.yaml`. Use `${ENV_VAR}` references and define the actual values in `.env`, which is excluded from version control.

---

## Full Configuration Reference

Below is a complete annotated `config.yaml` showing all available sections and their defaults.

---

### Agent

Core agent settings that control the workspace layout and execution limits.

```yaml
agent:
  workspace: "./workspace"    # Agent's sandboxed root directory
  data_dir: "./data"          # Checkpoints, session logs, scheduled tasks
  max_tool_iterations: 20     # Max tool calls the agent can make per turn
```

| Key | Default | Description |
|-----|---------|-------------|
| `workspace` | `./workspace` | Root directory for agent files: identity, memory, session logs, and any mounted host directories. |
| `data_dir` | `./data` | Directory for persistent data: checkpoints database, scheduled tasks, user allowlists. |
| `max_tool_iterations` | `20` | Safety limit on how many tools the agent can invoke in a single turn. Prevents runaway loops. |

---

### Provider

The LLM provider and model that powers the agent. CianaParrot supports multiple providers through LangChain's `init_chat_model()`.

```yaml
provider:
  name: "anthropic"           # anthropic | openai | openrouter | ollama | vllm | groq | google-genai
  model: "claude-sonnet-4-6"
  api_key: "${ANTHROPIC_API_KEY}"
  temperature: 0
  max_tokens: 8192
```

| Key | Default | Description |
|-----|---------|-------------|
| `name` | -- | Provider identifier. Determines which API client is used. |
| `model` | -- | Model name as recognized by the provider. |
| `api_key` | -- | API key, typically referenced from `.env`. |
| `temperature` | `0` | Sampling temperature. `0` for deterministic output, up to `2.0` for more creative responses. |
| `max_tokens` | `8192` | Maximum tokens per response. |

!!! tip "Switching providers"
    Changing the LLM is a two-line edit. For example, to use OpenAI:

    ```yaml
    provider:
      name: "openai"
      model: "gpt-4o"
      api_key: "${OPENAI_API_KEY}"
    ```

    For providers that require a custom endpoint (OpenRouter, Ollama, vLLM), add `base_url`:

    ```yaml
    provider:
      name: "openai"
      model: "anthropic/claude-sonnet-4-5"
      api_key: "${OPENROUTER_API_KEY}"
      base_url: "https://openrouter.ai/api/v1"
    ```

??? note "Supported providers"
    | Provider | `name` value | Example model | Required env var |
    |----------|-------------|---------------|------------------|
    | Anthropic | `anthropic` | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
    | OpenAI | `openai` | `gpt-4o` | `OPENAI_API_KEY` |
    | Google Gemini | `google-genai` | `gemini-2.0-flash` | `GOOGLE_API_KEY` |
    | Groq | `groq` | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
    | Ollama | `ollama` | `llama3` | -- (local) |
    | OpenRouter | `openai` | `anthropic/claude-sonnet-4-5` | `OPENROUTER_API_KEY` |
    | vLLM | `openai` | `your-model` | -- |

---

### Channels

Channel adapters define how the bot communicates with users. Currently, Telegram is the built-in channel.

```yaml
channels:
  telegram:
    enabled: true
    token: "${TELEGRAM_BOT_TOKEN}"
    trigger: "@Ciana"         # Required prefix in group chats
    allowed_users: []         # Empty = allow all
```

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `true` | Enable or disable the Telegram channel. |
| `token` | -- | Telegram bot token from [@BotFather](https://t.me/BotFather). |
| `trigger` | `@Ciana` | Prefix required in group chats. Messages in DMs always trigger a response regardless of this setting. |
| `allowed_users` | `[]` | List of allowed Telegram user IDs. An empty list allows everyone. |

!!! tip "Finding your Telegram user ID"
    Send a message to [@userinfobot](https://t.me/userinfobot) on Telegram to get your numeric user ID.

---

### Scheduler

The scheduler runs as a background task and executes timed actions -- cron jobs, intervals, and one-shot tasks. The agent can create tasks through natural language conversation.

```yaml
scheduler:
  enabled: true
  poll_interval: 60
  data_file: "./data/scheduled_tasks.json"
```

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `true` | Enable or disable the scheduler. |
| `poll_interval` | `60` | Seconds between checks for due tasks. |
| `data_file` | `./data/scheduled_tasks.json` | File where scheduled tasks are persisted. |

!!! info "Task types"
    The agent supports three task types:

    - **Cron** -- Standard cron expressions (e.g., `0 9 * * MON` for every Monday at 9 AM).
    - **Interval** -- Repeat every N seconds.
    - **Once** -- Run once at a specific ISO 8601 timestamp, then deactivate.

---

### MCP Servers

Connect external tools via the [Model Context Protocol](https://modelcontextprotocol.io). The format follows the LangChain MCP client configuration.

```yaml
mcp_servers: {}               # Empty by default
```

Example with two servers:

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

Each entry becomes an MCP server that the agent can call as a tool. The server name is used as a namespace prefix for its tools.

---

### Skills

The skills system lets you extend the agent with custom tools by dropping Python files into a directory.

```yaml
skills:
  enabled: true
  directory: "skills"         # Relative to workspace
```

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `true` | Enable or disable the skills system. |
| `directory` | `skills` | Directory to scan for skill modules. Each subdirectory with a `SKILL.md` and `skill.py` is registered. |

!!! tip "Bridge-dependent skills"
    Skills can declare `requires_bridge: "spotify"` in their `SKILL.md` frontmatter. If the named bridge is not configured in `gateway.bridges`, the skill is automatically filtered out at startup.

---

### Web

Built-in web tools for search and URL fetching.

```yaml
web:
  brave_api_key: "${BRAVE_API_KEY}"  # Optional
  fetch_timeout: 42
```

| Key | Default | Description |
|-----|---------|-------------|
| `brave_api_key` | -- | Brave Search API key. If not set, the agent falls back to DuckDuckGo (no API key required). |
| `fetch_timeout` | `42` | Timeout in seconds for URL fetch operations. |

---

### Transcription

Voice message transcription. When enabled, voice messages sent to the bot are automatically transcribed and processed as text.

```yaml
transcription:
  enabled: true
  provider: "openai"          # "openai" | "groq"
  model: "whisper-1"
  api_key: "${OPENAI_API_KEY}"
```

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `true` | Enable or disable voice transcription. |
| `provider` | `openai` | Transcription provider. Supported: `openai` (Whisper) and `groq`. |
| `model` | `whisper-1` | Model name for the transcription provider. |
| `api_key` | -- | API key for the transcription service. |

---

### Gateway

The gateway is a lightweight HTTP server that runs on the host machine and connects the sandboxed Docker container to host-side applications. Each bridge defines which CLI commands are allowed.

```yaml
gateway:
  enabled: true
  url: "http://host.docker.internal:9842"
  token: "${GATEWAY_TOKEN}"
  port: 9842
  default_timeout: 30
  bridges:
    claude-code:
      allowed_commands: ["claude"]
      allowed_cwd: ["~/Documents", "~/Projects"]
    apple-reminders:
      allowed_commands: ["remindctl"]
    spotify:
      allowed_commands: ["spogo"]
    things:
      allowed_commands: ["things"]
    sonos:
      allowed_commands: ["sonos"]
    imessage:
      allowed_commands: ["imsg"]
    bear-notes:
      allowed_commands: ["grizzly"]
    obsidian:
      allowed_commands: ["obsidian-cli"]
    openhue:
      allowed_commands: ["openhue"]
    camsnap:
      allowed_commands: ["camsnap"]
    peekaboo:
      allowed_commands: ["peekaboo"]
    blucli:
      allowed_commands: ["blu"]
    whatsapp:
      allowed_commands: ["wacli", "wacli-daemon"]
    1password:
      allowed_commands: ["op"]
```

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `true` | Enable or disable the gateway system. |
| `url` | `http://host.docker.internal:9842` | URL the agent uses to reach the gateway from inside Docker. |
| `token` | -- | Shared secret for authenticating requests. Must match the token used when starting the gateway. |
| `port` | `9842` | Port the gateway server listens on (host side). |
| `default_timeout` | `30` | Default command execution timeout in seconds. |

Each bridge entry under `bridges` defines:

| Key | Description |
|-----|-------------|
| `allowed_commands` | List of CLI commands this bridge is permitted to execute. Any other command is rejected. |
| `allowed_cwd` | *(Optional)* List of allowed working directories. Only used by bridges that support directory context (e.g., `claude-code`). |

!!! warning "Security model"
    The gateway only executes commands that appear in a bridge's `allowed_commands` list. A prompt injection against the agent cannot execute arbitrary commands -- only the specific CLIs you have explicitly allowed. Remove bridges you don't use to minimize the attack surface.

!!! tip "Adding a bridge"
    To connect a new host application:

    1. Install the CLI tool on your host machine.
    2. Add a bridge entry under `gateway.bridges` with the CLI in `allowed_commands`.
    3. Optionally create a skill in `skills/` with `requires_bridge` in the frontmatter.
    4. Run `make gateway` on the host and `make restart` for the bot.

---

### Claude Code

Configuration for the Claude Code integration, which provides interactive coding sessions via the Telegram `/cc` command.

```yaml
claude_code:
  enabled: true
  bridge_url: "http://host.docker.internal:9842"
  bridge_token: "${CC_BRIDGE_TOKEN}"
  projects_dir: "/app/.claude-projects"
  permission_mode: "bypassPermissions"
  timeout: 0                  # 0 = no timeout
```

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `true` | Enable or disable Claude Code mode. |
| `bridge_url` | `http://host.docker.internal:9842` | Gateway URL for Claude Code bridge communication. |
| `bridge_token` | -- | Authentication token for the Claude Code bridge. |
| `projects_dir` | `/app/.claude-projects` | Directory inside the container where project metadata is mounted (read-only from host `~/.claude/projects`). |
| `permission_mode` | `bypassPermissions` | Permission mode for Claude Code execution. `bypassPermissions` auto-approves tool use in non-interactive mode. |
| `timeout` | `0` | Execution timeout in seconds. `0` means no timeout -- the agent waits indefinitely for Claude Code to finish. |

---

### Logging

Controls the verbosity of log output.

```yaml
logging:
  level: "INFO"
```

| Key | Default | Description |
|-----|---------|-------------|
| `level` | `INFO` | Log level. One of: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |

!!! tip "Debugging"
    Set `level: "DEBUG"` to see detailed information about tool calls, LLM requests, routing decisions, and gateway communication. Useful when troubleshooting but produces verbose output.

---

## Environment Variable Expansion

Any value in `config.yaml` can reference an environment variable using `${VAR_NAME}` syntax. These are expanded at load time from the `.env` file (or the process environment).

```yaml
# In config.yaml
provider:
  api_key: "${ANTHROPIC_API_KEY}"

# In .env
ANTHROPIC_API_KEY=sk-ant-api03-...
```

If a referenced variable is not defined, the bot will fail at startup with a clear error message indicating which variable is missing.

---

## Validation

The configuration is validated at startup using Pydantic v2 models defined in `src/config.py`. The `load_config()` function returns a typed `AppConfig` instance. All consumer code uses attribute access:

```python
config.provider.model       # "claude-sonnet-4-6"
config.channels.telegram.trigger  # "@Ciana"
config.gateway.enabled      # True
```

If any required field is missing or a value has the wrong type, Pydantic raises a validation error with the exact field path and expected type before the bot starts.

---

## Next Steps

With your configuration in place, explore the [Architecture](../architecture/index.md) section to understand how messages flow through the system, or jump to the [Guides](../guides/index.md) to start customizing your setup.
