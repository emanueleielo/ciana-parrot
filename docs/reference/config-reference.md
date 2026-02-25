---
title: Config Reference
---

# Config Reference

Complete annotated `config.yaml` showing every option, its type, default value, and behavior. CianaParrot validates the entire configuration at startup using Pydantic v2 models -- invalid values produce clear error messages before the bot starts.

!!! warning "Secrets belong in `.env`"
    Never put API keys or tokens directly in `config.yaml`. Use `${ENV_VAR}` references and define the actual values in `.env`, which is excluded from version control.

!!! info "Env var expansion"
    All `${ENV_VAR}` patterns are expanded recursively from environment variables at load time. An unset variable expands to an empty string, which is then converted to `None` for optional fields.

---

## Full Annotated Example

```yaml title="config.yaml"
# ─────────────────────────────────────────────────────────────────────
# CianaParrot Configuration Reference
# All ${ENV_VAR} patterns are expanded from .env at load time
# Validated by Pydantic v2 models in src/config.py
# ─────────────────────────────────────────────────────────────────────

agent:
  workspace: "./workspace"           # (1)!
  data_dir: "./data"                 # (2)!
  max_tool_iterations: 20            # (3)!

provider:
  name: "anthropic"                  # (4)!
  model: "claude-sonnet-4-6"         # (5)!
  api_key: "${ANTHROPIC_API_KEY}"    # (6)!
  temperature: 0                     # (7)!
  max_tokens: 8192                   # (8)!
  base_url: ""                       # (9)!

channels:
  telegram:
    enabled: true                    # (10)!
    token: "${TELEGRAM_BOT_TOKEN}"   # (11)!
    trigger: "@Ciana"                # (12)!
    allowed_users: []                # (13)!

scheduler:
  enabled: true                      # (14)!
  poll_interval: 60                  # (15)!
  data_file: "./data/scheduled_tasks.json"  # (16)!

mcp_servers: {}                      # (17)!

skills:
  enabled: true                      # (18)!
  directory: "skills"                # (19)!

web:
  brave_api_key: "${BRAVE_API_KEY}"  # (20)!
  fetch_timeout: 30                  # (21)!

transcription:
  enabled: false                     # (22)!
  provider: "groq"                   # (23)!
  model: "whisper-large-v3-turbo"    # (24)!
  api_key: "${TRANSCRIPTION_API_KEY}" # (25)!
  base_url: ""                       # (26)!
  timeout: 30                        # (27)!

model_router:
  enabled: false                     # (28a)!
  default_tier: "standard"           # (28b)!
  tiers: {}                          # (28c)!

gateway:
  enabled: false                     # (28)!
  url: "http://host.docker.internal:9842"  # (29)!
  token: "${GATEWAY_TOKEN}"          # (30)!
  port: 9842                         # (31)!
  default_timeout: 30                # (32)!
  bridges:                           # (33)!
    claude-code:
      allowed_commands: ["claude"]   # (34)!
      allowed_cwd: ["~/Documents"]   # (35)!

claude_code:
  enabled: false                     # (36)!
  bridge_url: ""                     # (37)!
  bridge_token: ""                   # (38)!
  projects_dir: "~/.claude/projects" # (39)!
  permission_mode: ""                # (40)!
  timeout: 0                         # (41)!
  claude_path: "claude"              # (42)!
  state_file: "data/cc_user_states.json"  # (43)!

logging:
  level: "INFO"                      # (44)!
```

1. **`str`** -- Agent's sandboxed root directory. Contains identity files (`IDENTITY.md`, `AGENT.md`, `MEMORY.md`), session logs, and any host mounts.
2. **`str`** -- Directory for persistent data: checkpoints database, scheduled tasks JSON, session counters, user allowlists.
3. **`int`** -- Safety limit on tool calls per agent turn. Prevents runaway loops. Set higher for complex multi-step tasks.
4. **`str`** -- LLM provider identifier. Passed to LangChain's `init_chat_model()` as `"{name}:{model}"`. Supported: `anthropic`, `openai`, `openrouter`, `ollama`, `vllm`, `groq`, `google-genai`.
5. **`str`** -- Model identifier within the provider. Examples: `claude-sonnet-4-6`, `gpt-4o`, `llama3.3:70b`.
6. **`str?`** -- API key for the LLM provider. Empty string is converted to `None`. Required for cloud providers; not needed for local Ollama/vLLM.
7. **`float?`** -- Sampling temperature, `0.0`--`2.0`. `null` uses the provider's default. `0` gives deterministic output.
8. **`int?`** -- Maximum response tokens. `null` uses the provider's default.
9. **`str?`** -- Custom API endpoint. Empty string is converted to `None`. Required for OpenRouter (`https://openrouter.ai/api/v1`), Ollama (`http://localhost:11434`), or vLLM.
10. **`bool`** -- Enable or disable the Telegram channel entirely.
11. **`str`** -- Bot token obtained from [@BotFather](https://t.me/BotFather) on Telegram.
12. **`str`** -- Prefix required in group chats for the bot to respond. Case-insensitive matching. DMs always respond without a trigger.
13. **`list[str]`** -- Telegram user IDs allowed to interact. Empty list means all users are allowed. Numeric IDs are coerced to strings.
14. **`bool`** -- Enable the background task scheduler.
15. **`int`** -- Seconds between scheduler polls. Must be >= 1. Lower values mean faster task detection but higher CPU usage.
16. **`str`** -- Path to the JSON file where scheduled tasks are stored. Created automatically if missing.
17. **`dict`** -- MCP (Model Context Protocol) server configurations in LangChain format. Keys are server names; values follow the `MultiServerMCPClient` schema. See [`mcp_servers`](#mcp_servers) below.
18. **`bool`** -- Enable the skills system. When disabled, no skills are loaded from the directory.
19. **`str`** -- Virtual path relative to `workspace` where skill directories live. The agent sees this as `skills/my-skill/`.
20. **`str?`** -- Brave Search API key. Empty string is converted to `None`. When `None`, web search falls back to DuckDuckGo (no key required).
21. **`int`** -- HTTP timeout in seconds for the `web_fetch` tool.
22. **`bool`** -- Enable voice message transcription. When enabled, voice/audio messages are transcribed to text before being processed by the agent.
23. **`str`** -- Transcription provider. Must be `"groq"` or `"openai"`. Groq is faster; OpenAI supports more audio formats.
24. **`str`** -- Whisper model name. `whisper-large-v3-turbo` for Groq, `whisper-1` for OpenAI.
25. **`str?`** -- API key for the transcription provider. Empty string is converted to `None`.
26. **`str?`** -- Custom endpoint for the transcription provider. Empty string is converted to `None`.
27. **`int`** -- Timeout in seconds for transcription API calls.
28a. **`bool`** -- Enable multi-tier model routing. When enabled, the agent uses a `RoutingChatModel` that wraps all tier models and adds a `switch_model` tool. The `provider` section is ignored — the `default_tier` model is used instead.
28b. **`str`** -- The tier used by default. Must be a key in `tiers` when `enabled: true`. Validated at startup.
28c. **`dict[str, TierConfig]`** -- Map of tier names to model configurations. Each tier has the same fields as `provider` (`name`, `model`, `api_key`, `temperature`, `max_tokens`, `base_url`).
28. **`bool`** -- Enable the host gateway system. When enabled, the agent can execute commands on the host via the `host_execute` tool.
29. **`str?`** -- Gateway URL as seen from the Docker container. `host.docker.internal` resolves to the Docker host on macOS/Windows.
30. **`str?`** -- Bearer token for gateway authentication. Must match the token configured on the gateway server side.
31. **`int`** -- Port the gateway HTTP server listens on (host side).
32. **`int`** -- Default subprocess timeout in seconds. Overridden per-request if the agent passes a `timeout` argument.
33. **`dict[str, BridgeDefinition]`** -- Per-bridge allowlists. Each key is a bridge name; the value defines which binaries and working directories are permitted.
34. **`list[str]`** -- Binary names the bridge is allowed to execute (e.g., `["claude"]`, `["spogo"]`). The gateway rejects any command whose first token is not in this list.
35. **`list[str]`** -- Working directories the bridge is allowed to use. Supports `~` expansion. The gateway rejects requests with a `cwd` outside these paths. Empty list means no `cwd` restriction.
36. **`bool`** -- Enable the Claude Code integration (Telegram CC mode). Requires `gateway.enabled: true` and a `claude-code` bridge.
37. **`str?`** -- Gateway URL for the Claude Code bridge. Usually the same as `gateway.url`.
38. **`str?`** -- Auth token for the Claude Code bridge. Usually the same as `gateway.token`.
39. **`str`** -- Path to the Claude projects directory on the host. In Docker, mount this read-only (e.g., `/app/.claude-projects`).
40. **`str?`** -- Claude CLI permission mode. `"bypassPermissions"` auto-approves tool use (non-interactive). Empty string is converted to `None`.
41. **`int`** -- Timeout in seconds for Claude Code operations. `0` means no timeout (wait indefinitely).
42. **`str`** -- Path to the `claude` binary on the host. Only relevant when the gateway executes the command.
43. **`str`** -- Path to the JSON file that persists per-user CC state (active project, session, model, effort).
44. **`str`** -- Python logging level. Must be one of: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Case-insensitive (normalized to uppercase).

---

## Section Details

### `agent`

Core agent settings that control the workspace layout and execution limits.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `workspace` | `str` | `"./workspace"` | Agent's sandboxed root directory |
| `data_dir` | `str` | `"./data"` | Directory for checkpoints, session logs, tasks |
| `max_tool_iterations` | `int` | `20` | Max tool calls the agent can make per turn |

---

### `provider`

The LLM provider and model that powers the agent. CianaParrot supports multiple providers through LangChain's `init_chat_model("{provider}:{model}")`.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `name` | `str` | `"anthropic"` | Provider: `anthropic`, `openai`, `openrouter`, `ollama`, `vllm`, `groq`, `google-genai` |
| `model` | `str` | `"claude-sonnet-4-6"` | Model identifier within the provider |
| `api_key` | `str?` | `None` | API key (empty string converted to `None`) |
| `temperature` | `float?` | `None` | Sampling temperature, `0.0`--`2.0` |
| `max_tokens` | `int?` | `None` | Max response tokens |
| `base_url` | `str?` | `None` | Custom API endpoint (empty string converted to `None`) |

??? example "Provider examples"

    === "Anthropic (default)"

        ```yaml
        provider:
          name: "anthropic"
          model: "claude-sonnet-4-6"
          api_key: "${ANTHROPIC_API_KEY}"
          temperature: 0
          max_tokens: 8192
        ```

    === "OpenAI"

        ```yaml
        provider:
          name: "openai"
          model: "gpt-4o"
          api_key: "${OPENAI_API_KEY}"
        ```

    === "OpenRouter"

        ```yaml
        provider:
          name: "openrouter"
          model: "anthropic/claude-sonnet-4-6"
          api_key: "${OPENROUTER_API_KEY}"
          base_url: "https://openrouter.ai/api/v1"
        ```

    === "Ollama (local)"

        ```yaml
        provider:
          name: "ollama"
          model: "llama3.3:70b"
          base_url: "http://localhost:11434"
        ```

    === "Groq"

        ```yaml
        provider:
          name: "groq"
          model: "llama-3.3-70b-versatile"
          api_key: "${GROQ_API_KEY}"
        ```

    === "Google Gemini"

        ```yaml
        provider:
          name: "google-genai"
          model: "gemini-2.5-pro"
          api_key: "${GOOGLE_API_KEY}"
        ```

!!! note "Validation"
    `temperature` must be between `0.0` and `2.0` if set. Values outside this range cause a startup validation error.

---

### `channels.telegram`

Telegram bot configuration. The bot uses manual polling (not webhooks) to share the asyncio event loop.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `false` | Enable the Telegram channel |
| `token` | `str` | `""` | Bot token from [@BotFather](https://t.me/BotFather) |
| `trigger` | `str` | `"@Ciana"` | Prefix required in group chats |
| `allowed_users` | `list[str]` | `[]` | User IDs; empty = allow all |

!!! tip "Finding your Telegram user ID"
    Send a message to [@userinfobot](https://t.me/userinfobot) to get your numeric Telegram user ID. Add it to `allowed_users` to restrict access.

---

### `scheduler`

Background task scheduler supporting cron expressions, fixed intervals, and one-shot timers. Tasks are stored in a JSON file and survive container restarts.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `false` | Enable the task scheduler |
| `poll_interval` | `int` | `60` | Seconds between task checks (must be >= 1) |
| `data_file` | `str` | `"./data/scheduled_tasks.json"` | Path to the tasks JSON file |

---

### `mcp_servers`

MCP (Model Context Protocol) server configurations. Each entry defines an external tool server that the agent can connect to.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| *(root)* | `dict[str, dict]` | `{}` | Server name to config mapping |

The value format follows `langchain-mcp-adapters`' `MultiServerMCPClient` schema:

```yaml
mcp_servers:
  filesystem:
    transport: "stdio"            # "stdio" or "sse"
    command: "npx"                # Binary to run
    args:                         # Command-line arguments
      - "-y"
      - "@modelcontextprotocol/server-filesystem"
      - "/data"

  remote_server:
    transport: "sse"              # Server-Sent Events transport
    url: "http://localhost:3001/sse"
```

---

### `skills`

Controls the DeepAgents skill system. Skills are loaded from subdirectories of the skills directory inside the workspace.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `true` | Enable the skills system |
| `directory` | `str` | `"skills"` | Virtual path relative to `workspace` |

See the [Skill Format Reference](skill-format.md) for details on creating skills.

---

### `web`

Web search and fetch tools configuration.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `brave_api_key` | `str?` | `None` | Brave Search API key; falls back to DuckDuckGo if `None` |
| `fetch_timeout` | `int` | `30` | HTTP timeout in seconds for `web_fetch` |

---

### `transcription`

Voice message transcription using OpenAI Whisper or Groq. When enabled, voice and audio messages sent to the bot are automatically transcribed and processed as text.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `false` | Enable voice transcription |
| `provider` | `str` | `"groq"` | Provider: `"groq"` or `"openai"` |
| `model` | `str` | `"whisper-large-v3-turbo"` | Whisper model name |
| `api_key` | `str?` | `None` | Provider API key |
| `base_url` | `str?` | `None` | Custom endpoint |
| `timeout` | `int` | `30` | API call timeout in seconds |

!!! note "Validation"
    `provider` must be `"groq"` or `"openai"`. Any other value causes a startup error.

---

### `model_router`

Multi-tier model routing with in-chat model switching. When enabled, the agent runs on a `RoutingChatModel` that wraps multiple LLM tiers behind a single interface. The agent can call `switch_model(tier="expert")` to upgrade to a stronger model mid-conversation — the switch takes effect on the next agent step with full tools, memory, and context preserved.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `false` | Enable model routing (replaces `provider` as the agent's LLM) |
| `default_tier` | `str` | `"standard"` | Tier used by default. Must exist in `tiers` when enabled |
| `tiers` | `dict[str, TierConfig]` | `{}` | Map of tier names to model configurations |

#### `tiers.<name>` (TierConfig)

Each tier has the same fields as `provider`:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `name` | `str` | — | Provider name (`openai`, `anthropic`, `google-genai`, etc.) |
| `model` | `str` | — | Model identifier |
| `api_key` | `str?` | `None` | API key |
| `temperature` | `float?` | `None` | Sampling temperature, `0.0`--`2.0` |
| `max_tokens` | `int?` | `None` | Max response tokens |
| `base_url` | `str?` | `None` | Custom API endpoint |

??? example "Model router configuration"

    ```yaml
    model_router:
      enabled: true
      default_tier: "standard"
      tiers:
        lite:
          name: "openai"
          model: "gpt-4o-mini"
          api_key: "${OPENAI_API_KEY}"
        standard:
          name: "openai"
          model: "gpt-4o"
          api_key: "${OPENAI_API_KEY}"
        advanced:
          name: "openai"
          model: "gpt-5"
          api_key: "${OPENAI_API_KEY}"
        expert:
          name: "openai"
          model: "gpt-5"
          api_key: "${OPENAI_API_KEY}"
    ```

!!! note "Validation"
    When `enabled: true`, `default_tier` must be a key in `tiers`. Empty `default_tier` is rejected. These are validated at startup — misconfiguration produces a clear error before the bot starts.

!!! tip "Override in config.local.yaml"
    Keep `model_router` disabled in `config.yaml` and enable it in `config.local.yaml` (gitignored) with your API keys and tier setup.

---

### `gateway`

The host gateway system allows the agent (running inside Docker) to execute commands on the host machine through a secure HTTP bridge.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `false` | Enable the gateway system |
| `url` | `str?` | `None` | Gateway URL from Docker's perspective |
| `token` | `str?` | `None` | Bearer auth token |
| `port` | `int` | `9842` | Gateway server listen port (host side) |
| `default_timeout` | `int` | `30` | Default subprocess timeout in seconds |
| `bridges` | `dict[str, BridgeDefinition]` | `{}` | Per-bridge command and directory allowlists |

#### `bridges.<name>` (BridgeDefinition)

Each bridge defines an allowlist of commands and working directories:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `allowed_commands` | `list[str]` | `[]` | Binary names permitted for this bridge |
| `allowed_cwd` | `list[str]` | `[]` | Allowed working directories (supports `~` expansion) |

??? example "Bridge configuration examples"

    ```yaml
    bridges:
      claude-code:
        allowed_commands: ["claude"]
        allowed_cwd: ["~/Documents", "~/Projects"]
      spotify:
        allowed_commands: ["spogo"]
      apple-reminders:
        allowed_commands: ["remindctl"]
      things:
        allowed_commands: ["things"]
      sonos:
        allowed_commands: ["sonos"]
      imessage:
        allowed_commands: ["imsg"]
      whatsapp:
        allowed_commands: ["wacli", "wacli-daemon"]
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
      1password:
        allowed_commands: ["op"]
    ```

---

### `claude_code`

Claude Code integration for running full Claude Code sessions from Telegram. Requires the gateway to be enabled with a `claude-code` bridge configured.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | `false` | Enable Claude Code integration |
| `bridge_url` | `str?` | `None` | Gateway URL for CC bridge |
| `bridge_token` | `str?` | `None` | Auth token for CC bridge |
| `projects_dir` | `str` | `"~/.claude/projects"` | Claude projects directory |
| `permission_mode` | `str?` | `None` | Claude CLI permission flag (e.g., `"bypassPermissions"`) |
| `timeout` | `int` | `0` | Timeout in seconds; `0` = no timeout |
| `claude_path` | `str` | `"claude"` | Path to the `claude` binary |
| `state_file` | `str` | `"data/cc_user_states.json"` | Persistent user state file |

---

### `logging`

Python logging configuration.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `level` | `str` | `"INFO"` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

!!! note "Validation"
    The level is normalized to uppercase. Invalid values cause a startup error listing the valid options.

---

## Type Legend

| Notation | Meaning |
|----------|---------|
| `str` | Required string |
| `str?` | Optional string (`None` if empty or unset) |
| `int` | Required integer |
| `int?` | Optional integer |
| `float?` | Optional float |
| `bool` | Boolean (`true` / `false`) |
| `list[str]` | List of strings |
| `dict` | Dictionary / mapping |

---

## Source

Configuration models are defined in [`src/config.py`](https://github.com/emanueleielo/ciana-parrot/blob/main/src/config.py). The top-level model is `AppConfig`, which composes all section models:

```python title="src/config.py (summary)"
class AppConfig(BaseModel):
    agent: AgentConfig
    provider: ProviderConfig
    channels: ChannelsConfig
    scheduler: SchedulerConfig
    mcp_servers: dict[str, dict[str, Any]]
    skills: SkillsConfig
    web: WebConfig
    transcription: TranscriptionConfig
    model_router: ModelRouterConfig
    gateway: GatewayConfig
    claude_code: ClaudeCodeConfig
    logging: LoggingConfig
```
