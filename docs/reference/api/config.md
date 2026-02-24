# Config Models

::: src.config

---

## Overview

All configuration is defined as Pydantic v2 `BaseModel` subclasses and loaded from a single `config.yaml` file. Environment variable expansion (`${VAR}`) is supported throughout all string values.

**Source file:** `src/config.py`

---

## `load_config(path="config.yaml") -> AppConfig`

Load and validate configuration from a YAML file.

```python
def load_config(path: str = "config.yaml") -> AppConfig:
    """Load and validate config from YAML file."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    expanded = _walk_expand(raw or {})
    return AppConfig.model_validate(expanded)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | `"config.yaml"` | Path to the YAML configuration file |

**Returns:** Validated `AppConfig` instance.

**Raises:** `FileNotFoundError` if the config file does not exist; `pydantic.ValidationError` on invalid config.

**Process:**

1. Read YAML file via `yaml.safe_load()`
2. Recursively expand `${VAR}` patterns with `os.environ.get(var, "")`
3. Validate via `AppConfig.model_validate()`

---

## `AppConfig`

Top-level configuration model. All sections are optional and default to their respective model defaults.

```python
class AppConfig(BaseModel):
    agent: AgentConfig = Field(default_factory=AgentConfig)
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    mcp_servers: dict[str, dict[str, Any]] = Field(default_factory=dict)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    claude_code: ClaudeCodeConfig = Field(default_factory=ClaudeCodeConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `agent` | `AgentConfig` | `AgentConfig()` | Agent workspace and iteration settings |
| `provider` | `ProviderConfig` | `ProviderConfig()` | LLM provider configuration |
| `channels` | `ChannelsConfig` | `ChannelsConfig()` | Channel adapters |
| `scheduler` | `SchedulerConfig` | `SchedulerConfig()` | Task scheduler settings |
| `mcp_servers` | `dict[str, dict[str, Any]]` | `{}` | MCP server configurations (passed to `MultiServerMCPClient`) |
| `skills` | `SkillsConfig` | `SkillsConfig()` | Skill loading configuration |
| `web` | `WebConfig` | `WebConfig()` | Web tools configuration |
| `transcription` | `TranscriptionConfig` | `TranscriptionConfig()` | Voice transcription settings |
| `gateway` | `GatewayConfig` | `GatewayConfig()` | Host gateway configuration |
| `claude_code` | `ClaudeCodeConfig` | `ClaudeCodeConfig()` | Claude Code bridge settings |
| `logging` | `LoggingConfig` | `LoggingConfig()` | Logging level |

---

## `AgentConfig`

Agent workspace and execution settings.

```python
class AgentConfig(BaseModel):
    workspace: str = "./workspace"
    data_dir: str = "./data"
    max_tool_iterations: int = 20
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `workspace` | `str` | `"./workspace"` | Root directory for agent file operations |
| `data_dir` | `str` | `"./data"` | Directory for runtime data (checkpoints, sessions, tasks) |
| `max_tool_iterations` | `int` | `20` | Maximum tool call iterations per agent invocation |

---

## `ProviderConfig`

LLM provider configuration.

```python
class ProviderConfig(BaseModel):
    name: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    api_key: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    base_url: Optional[str] = None
```

| Field | Type | Default | Validator | Description |
|-------|------|---------|-----------|-------------|
| `name` | `str` | `"anthropic"` | -- | Provider name (e.g. `"anthropic"`, `"openai"`, `"google-genai"`) |
| `model` | `str` | `"claude-sonnet-4-6"` | -- | Model identifier |
| `api_key` | `Optional[str]` | `None` | Empty string to `None` | API key for the provider |
| `temperature` | `Optional[float]` | `None` | Must be 0.0--2.0 | Sampling temperature |
| `max_tokens` | `Optional[int]` | `None` | -- | Maximum output tokens |
| `base_url` | `Optional[str]` | `None` | Empty string to `None` | Custom API base URL |

**Validators:**

- `api_key`, `base_url`: empty strings are converted to `None`
- `temperature`: must be between 0.0 and 2.0 (inclusive) if set

---

## `TelegramChannelConfig`

Telegram channel settings.

```python
class TelegramChannelConfig(BaseModel):
    enabled: bool = False
    token: str = ""
    trigger: str = "@Ciana"
    allowed_users: list[str] = Field(default_factory=list)
```

| Field | Type | Default | Validator | Description |
|-------|------|---------|-----------|-------------|
| `enabled` | `bool` | `False` | -- | Enable Telegram channel |
| `token` | `str` | `""` | -- | Telegram bot token |
| `trigger` | `str` | `"@Ciana"` | -- | Prefix required in group chats to trigger the bot |
| `allowed_users` | `list[str]` | `[]` | Coerces items to `str` | User IDs allowed to use the bot (empty = allow all) |

**Validators:**

- `allowed_users`: all items are coerced to `str` (handles integer user IDs in YAML)

---

## `ChannelsConfig`

Container for all channel configurations.

```python
class ChannelsConfig(BaseModel):
    telegram: TelegramChannelConfig = Field(default_factory=TelegramChannelConfig)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `telegram` | `TelegramChannelConfig` | `TelegramChannelConfig()` | Telegram channel config |

---

## `SchedulerConfig`

Task scheduler settings.

```python
class SchedulerConfig(BaseModel):
    enabled: bool = False
    poll_interval: int = 60
    data_file: str = "./data/scheduled_tasks.json"
```

| Field | Type | Default | Validator | Description |
|-------|------|---------|-----------|-------------|
| `enabled` | `bool` | `False` | -- | Enable the scheduler |
| `poll_interval` | `int` | `60` | Must be >= 1 | Seconds between scheduler polls |
| `data_file` | `str` | `"./data/scheduled_tasks.json"` | -- | Path to the tasks JSON file |

---

## `SkillsConfig`

Skill loading settings.

```python
class SkillsConfig(BaseModel):
    enabled: bool = True
    directory: str = "skills"
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `True` | Enable skill loading |
| `directory` | `str` | `"skills"` | Virtual path relative to workspace |

---

## `WebConfig`

Web tools configuration.

```python
class WebConfig(BaseModel):
    brave_api_key: Optional[str] = None
    fetch_timeout: int = 30
```

| Field | Type | Default | Validator | Description |
|-------|------|---------|-----------|-------------|
| `brave_api_key` | `Optional[str]` | `None` | Empty string to `None` | Brave Search API key (enables Brave; `None` = DuckDuckGo fallback) |
| `fetch_timeout` | `int` | `30` | -- | HTTP timeout for `web_fetch` in seconds |

---

## `TranscriptionConfig`

Voice message transcription settings.

```python
class TranscriptionConfig(BaseModel):
    enabled: bool = False
    provider: str = "groq"
    model: str = "whisper-large-v3-turbo"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: int = 30
```

| Field | Type | Default | Validator | Description |
|-------|------|---------|-----------|-------------|
| `enabled` | `bool` | `False` | -- | Enable voice transcription |
| `provider` | `str` | `"groq"` | Must be `"groq"` or `"openai"` | Transcription provider |
| `model` | `str` | `"whisper-large-v3-turbo"` | -- | Whisper model identifier |
| `api_key` | `Optional[str]` | `None` | Empty string to `None` | Provider API key |
| `base_url` | `Optional[str]` | `None` | Empty string to `None` | Custom API base URL |
| `timeout` | `int` | `30` | -- | Transcription timeout in seconds |

---

## `BridgeDefinition`

Per-bridge security configuration for the gateway.

```python
class BridgeDefinition(BaseModel):
    allowed_commands: list[str] = Field(default_factory=list)
    allowed_cwd: list[str] = Field(default_factory=list)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `allowed_commands` | `list[str]` | `[]` | Command basenames allowed for this bridge |
| `allowed_cwd` | `list[str]` | `[]` | Filesystem paths the bridge can use as working directories |

---

## `GatewayConfig`

Host gateway settings.

```python
class GatewayConfig(BaseModel):
    enabled: bool = False
    url: Optional[str] = None
    token: Optional[str] = None
    port: int = 9842
    default_timeout: int = 30
    bridges: dict[str, BridgeDefinition] = Field(default_factory=dict)
```

| Field | Type | Default | Validator | Description |
|-------|------|---------|-----------|-------------|
| `enabled` | `bool` | `False` | -- | Enable gateway integration |
| `url` | `Optional[str]` | `None` | Empty string to `None` | Gateway URL (e.g. `"http://host.docker.internal:9842"`) |
| `token` | `Optional[str]` | `None` | Empty string to `None` | Bearer token for authentication |
| `port` | `int` | `9842` | -- | Port the gateway server listens on |
| `default_timeout` | `int` | `30` | -- | Default subprocess timeout in seconds |
| `bridges` | `dict[str, BridgeDefinition]` | `{}` | -- | Per-bridge command and cwd allowlists |

**Example config.yaml:**

```yaml
gateway:
  enabled: true
  url: "http://host.docker.internal:9842"
  token: "${GATEWAY_TOKEN}"
  port: 9842
  default_timeout: 30
  bridges:
    claude-code:
      allowed_commands: [claude]
      allowed_cwd: ["~/Projects", "~/Documents"]
    apple-notes:
      allowed_commands: [memo]
```

---

## `ClaudeCodeConfig`

Claude Code bridge settings.

```python
class ClaudeCodeConfig(BaseModel):
    enabled: bool = False
    bridge_url: Optional[str] = None
    bridge_token: Optional[str] = None
    projects_dir: str = "~/.claude/projects"
    permission_mode: Optional[str] = None
    timeout: int = 0
    claude_path: str = "claude"
    state_file: str = "data/cc_user_states.json"
```

| Field | Type | Default | Validator | Description |
|-------|------|---------|-----------|-------------|
| `enabled` | `bool` | `False` | -- | Enable Claude Code bridge |
| `bridge_url` | `Optional[str]` | `None` | Empty string to `None` | Gateway URL override (falls back to `gateway.url`) |
| `bridge_token` | `Optional[str]` | `None` | Empty string to `None` | Auth token override (falls back to `gateway.token`) |
| `projects_dir` | `str` | `"~/.claude/projects"` | -- | Path to Claude Code projects directory |
| `permission_mode` | `Optional[str]` | `None` | Empty string to `None` | Claude Code `--permission-mode` flag value |
| `timeout` | `int` | `0` | -- | Command timeout in seconds (0 = no limit) |
| `claude_path` | `str` | `"claude"` | -- | Path to `claude` CLI binary |
| `state_file` | `str` | `"data/cc_user_states.json"` | -- | Path for persisting per-user session state |

---

## `LoggingConfig`

Logging settings.

```python
class LoggingConfig(BaseModel):
    level: str = "INFO"
```

| Field | Type | Default | Validator | Description |
|-------|------|---------|-----------|-------------|
| `level` | `str` | `"INFO"` | Must be one of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`; auto-uppercased | Python logging level |
