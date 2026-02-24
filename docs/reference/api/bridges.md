# Bridges API

::: src.gateway.bridges.claude_code

---

## Overview

The bridges layer provides integrations with external tools accessible through the host gateway. Currently, the primary bridge is `ClaudeCodeBridge`, which manages Claude Code CLI sessions per user, enabling Telegram-driven code interactions.

**Source files:**

- `src/gateway/bridges/claude_code/bridge.py` -- bridge implementation
- `src/gateway/bridges/claude_code/__init__.py` -- factory function

---

## `CCResponse`

:octicons-file-code-16: `src/gateway/bridges/claude_code/bridge.py`

Parsed response from Claude Code CLI. Contains either structured events (normal response) or an error string.

```python
@dataclass
class CCResponse:
    """Parsed response from Claude Code CLI."""
    events: list = field(default_factory=list)
    error: str = ""
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `events` | `list` | `[]` | List of `TextEvent`, `ThinkingEvent`, or `ToolCallEvent` instances |
| `error` | `str` | `""` | Error message if the command failed |

---

## `ProjectInfo`

:octicons-file-code-16: `src/gateway/bridges/claude_code/bridge.py`

Metadata for a Claude Code project discovered from `~/.claude/projects/`.

```python
@dataclass
class ProjectInfo:
    encoded_name: str
    real_path: str
    display_name: str
    conversation_count: int
    last_activity: Optional[datetime] = None
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `encoded_name` | `str` | *required* | URL-safe encoded project directory name |
| `real_path` | `str` | *required* | Actual filesystem path extracted from JSONL `cwd` field |
| `display_name` | `str` | *required* | Human-readable project name (last path segment) |
| `conversation_count` | `int` | *required* | Number of `.jsonl` conversation files |
| `last_activity` | `Optional[datetime]` | `None` | Timestamp of the most recently modified conversation |

---

## `ConversationInfo`

:octicons-file-code-16: `src/gateway/bridges/claude_code/bridge.py`

Metadata for a single conversation session within a project.

```python
@dataclass
class ConversationInfo:
    session_id: str
    first_message: str
    timestamp: datetime
    message_count: int
    git_branch: str = ""
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `session_id` | `str` | *required* | JSONL filename stem (unique session identifier) |
| `first_message` | `str` | *required* | Preview of the first user message (max 120 chars) |
| `timestamp` | `datetime` | *required* | When the conversation started |
| `message_count` | `int` | *required* | Number of user messages in the conversation |
| `git_branch` | `str` | `""` | Git branch active during the session |

---

## `UserSession`

:octicons-file-code-16: `src/gateway/bridges/claude_code/bridge.py`

Per-user state for Claude Code mode. Persisted to disk via `JsonStore` so sessions survive container restarts.

```python
@dataclass
class UserSession:
    mode: str = "ciana"
    active_project: Optional[str] = None
    active_project_path: Optional[str] = None
    active_session_id: Optional[str] = None
    active_model: Optional[str] = None
    active_effort: Optional[str] = None
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | `str` | `"ciana"` | Current mode: `"ciana"` (normal) or `"claude_code"` |
| `active_project` | `Optional[str]` | `None` | Encoded project name |
| `active_project_path` | `Optional[str]` | `None` | Real filesystem path of the active project |
| `active_session_id` | `Optional[str]` | `None` | Active conversation session ID |
| `active_model` | `Optional[str]` | `None` | Override model for Claude Code (e.g. `"claude-sonnet-4-6"`) |
| `active_effort` | `Optional[str]` | `None` | Effort level override (e.g. `"low"`, `"medium"`, `"high"`) |

---

## `ClaudeCodeBridge`

:octicons-file-code-16: `src/gateway/bridges/claude_code/bridge.py`

Manages Claude Code CLI interactions, either locally or via the host gateway bridge. Handles per-user session state, project/conversation discovery, and NDJSON response parsing.

### Constructor

```python
class ClaudeCodeBridge:
    def __init__(self, config: AppConfig):
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `config` | `AppConfig` | Full application config; reads `config.claude_code` and `config.gateway` sections |

Initializes from `config.claude_code`:

- `claude_path` -- path to the `claude` CLI binary
- `projects_dir` -- path to `~/.claude/projects/`
- `timeout` -- command timeout in seconds (0 = no limit)
- `permission_mode` -- Claude Code permission mode
- `bridge_url` / `bridge_token` -- gateway connection (falls back to `config.gateway.url` / `.token`)
- `state_file` -- path for persisting user session state

### Methods

#### `get_user_state(user_id) -> UserSession` {: #bridge-get-user-state }

Get or create the session state for a user.

```python
def get_user_state(self, user_id: str) -> UserSession:
    if user_id not in self._user_states:
        self._user_states[user_id] = UserSession()
    return self._user_states[user_id]
```

#### `is_claude_code_mode(user_id) -> bool` {: #bridge-is-claude-code-mode }

Check if a user is currently in Claude Code mode.

```python
def is_claude_code_mode(self, user_id: str) -> bool:
    state = self._user_states.get(user_id)
    return state is not None and state.mode == "claude_code"
```

#### `exit_mode(user_id) -> None` {: #bridge-exit-mode }

Exit Claude Code mode for a user, resetting their state and removing persisted data.

```python
def exit_mode(self, user_id: str) -> None:
    if user_id in self._user_states:
        self._user_states[user_id] = UserSession()
    self._store.delete(user_id)
```

#### `list_projects() -> list[ProjectInfo]` {: #bridge-list-projects }

Scan `~/.claude/projects/` and return project metadata sorted by most recent activity.

```python
def list_projects(self) -> list[ProjectInfo]:
    """Scan ~/.claude/projects/ and return project info sorted by most recent."""
```

**Returns:** List of `ProjectInfo` sorted by `last_activity` (newest first). Returns empty list if the projects directory does not exist.

#### `list_conversations(project_encoded) -> list[ConversationInfo]` {: #bridge-list-conversations }

Parse JSONL files for a project and return conversation metadata.

```python
def list_conversations(self, project_encoded: str) -> list[ConversationInfo]:
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_encoded` | `str` | URL-encoded project directory name |

**Returns:** List of `ConversationInfo` sorted by `timestamp` (newest first).

#### `activate_session(user_id, project_encoded, project_path, session_id=None)` {: #bridge-activate-session }

Set a user into Claude Code mode for a specific project and optional session.

```python
def activate_session(self, user_id: str, project_encoded: str,
                     project_path: str, session_id: Optional[str] = None) -> None:
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_id` | `str` | *required* | Telegram user ID |
| `project_encoded` | `str` | *required* | Encoded project directory name |
| `project_path` | `str` | *required* | Real filesystem path |
| `session_id` | `Optional[str]` | `None` | Resume a specific session, or `None` for new conversation |

#### `set_model(user_id, model)` {: #bridge-set-model }

Set the model preference for a user's Claude Code session.

```python
def set_model(self, user_id: str, model: Optional[str]) -> None:
```

#### `set_effort(user_id, effort)` {: #bridge-set-effort }

Set the effort level for a user's Claude Code session.

```python
def set_effort(self, user_id: str, effort: Optional[str]) -> None:
```

#### `send_message(user_id, text) -> CCResponse` {: #bridge-send-message }

Send a message to Claude Code CLI and return the parsed response. Automatically detects new session IDs when starting a new conversation.

```python
async def send_message(self, user_id: str, text: str) -> CCResponse:
    """Send a message to Claude Code CLI and return the response."""
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `user_id` | `str` | User whose session state to use |
| `text` | `str` | Message to send to Claude Code |

**Returns:** `CCResponse` with either structured events or an error.

#### `fork_session(user_id) -> CCResponse` {: #bridge-fork-session }

Fork the current session (creates a new conversation continuing from the current one).

```python
async def fork_session(self, user_id: str) -> CCResponse:
    """Fork the current session (compact workaround)."""
```

**Returns:** `CCResponse`. Updates the user's `active_session_id` to the new forked session.

#### `check_available() -> tuple[bool, str]` {: #bridge-check-available }

Check if Claude Code is accessible, either via the bridge gateway or the local CLI.

```python
async def check_available(self) -> tuple[bool, str]:
```

**Returns:** `(is_available, status_message)` -- e.g. `(True, "Gateway OK -- bridges: claude-code")` or `(False, "Cannot connect to Claude Code bridge")`.

---

## `setup_bridge(config, channel)`

:octicons-file-code-16: `src/gateway/bridges/claude_code/__init__.py`

Factory function that creates the Claude Code bridge, checks availability, and registers the mode handler on a Telegram channel.

```python
async def setup_bridge(config, channel) -> None:
    """Wire Claude Code bridge to a channel, if enabled."""
    if not config.claude_code.enabled:
        return

    from ....channels.telegram.handlers.claude_code import ClaudeCodeHandler

    bridge = ClaudeCodeBridge(config)
    available, version = await bridge.check_available()
    if available:
        logger.info("Claude Code bridge ready: %s", version)
    else:
        logger.warning("Claude Code bridge not reachable: %s", version)

    channel.register_mode_handler(lambda app, send: ClaudeCodeHandler(bridge, app, send))
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `config` | `AppConfig` | Full application config |
| `channel` | `TelegramChannel` | Channel instance to register the mode handler on |

**Behavior:**

1. Returns immediately if `config.claude_code.enabled` is `False`
2. Creates a `ClaudeCodeBridge` instance
3. Checks availability (logs warning if unreachable)
4. Registers a `ClaudeCodeHandler` factory on the channel
