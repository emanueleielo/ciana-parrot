# Tools API

::: src.tools.web
::: src.tools.cron
::: src.tools.host

---

## Overview

Tools are agent-callable functions decorated with `@tool` from `langchain_core.tools`. Each module follows the same pattern: an `init_*()` function sets module-level globals at startup, then `@tool`-decorated async functions use those globals at runtime.

**Source files:**

- `src/tools/web.py` -- web search and URL fetching
- `src/tools/cron.py` -- scheduled task management
- `src/tools/host.py` -- host command execution via gateway

---

## Web Tools

:octicons-file-code-16: `src/tools/web.py`

### Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_CONTENT_LENGTH` | `15,000` | Maximum characters returned from `web_fetch` |

### `init_web_tools(config)`

Initialize web tools with configuration values. Must be called once at startup.

```python
def init_web_tools(config: WebConfig) -> None:
    """Initialize web tools with config values."""
    global _brave_api_key, _fetch_timeout
    _brave_api_key = config.brave_api_key
    _fetch_timeout = config.fetch_timeout
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `config` | `WebConfig` | Web configuration (Brave API key, fetch timeout) |

**Module-level state set:**

| Variable | Type | Description |
|----------|------|-------------|
| `_brave_api_key` | `Optional[str]` | Brave Search API key (enables Brave; `None` = DuckDuckGo fallback) |
| `_fetch_timeout` | `int` | HTTP timeout for `web_fetch` in seconds (default: 30) |

### `web_search(query, max_results=5) -> str` {: #web-search }

Search the web for information. Uses Brave Search API if a key is configured, otherwise falls back to DuckDuckGo HTML scraping.

```python
@tool
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for information. Returns a summary of search results."""
    if _brave_api_key:
        return await _brave_search(query, max_results)
    return await _ddg_search(query, max_results)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | *required* | Search query string |
| `max_results` | `int` | `5` | Maximum number of results to return |

**Returns:** Formatted string with titles, URLs, and descriptions separated by `---`. Returns `"No results found."` if no results.

**Search backends:**

- **Brave Search** (`_brave_api_key` set): calls `https://api.search.brave.com/res/v1/web/search`
- **DuckDuckGo** (fallback): scrapes `https://html.duckduckgo.com/html/` and parses result links

### `web_fetch(url) -> str` {: #web-fetch }

Fetch a URL and return its content as clean markdown. HTML pages are converted via `markdownify`; other content types are returned as plain text.

```python
@tool
async def web_fetch(url: str) -> str:
    """Fetch a URL and return its content as clean markdown."""
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | `str` | URL to fetch |

**Returns:** Markdown content truncated at 15,000 characters, or `"Error fetching {url}: {error}"` on failure.

**Behavior:**

- Follows redirects
- Strips `<script>`, `<style>`, `<nav>`, `<footer>` tags from HTML
- Truncates with `"... (truncated)"` suffix if content exceeds `MAX_CONTENT_LENGTH`

---

## Cron Tools

:octicons-file-code-16: `src/tools/cron.py`

### Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `PROMPT_PREVIEW_LEN` | `60` | Max characters shown in task prompt previews |

### `init_cron_tools(config)`

Initialize cron tools with scheduler configuration. Creates the shared async lock for file operations.

```python
def init_cron_tools(config: SchedulerConfig) -> None:
    """Initialize cron tools with config."""
    global _data_file, _tasks_lock
    _data_file = config.data_file
    _tasks_lock = asyncio.Lock()
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `config` | `SchedulerConfig` | Scheduler configuration (data file path) |

### `set_current_context(channel, chat_id)`

Set the current channel/chat context for new tasks. Called by `MessageRouter` per-message so that tasks created during that message know where to send results.

```python
def set_current_context(channel: str, chat_id: str) -> None:
    """Set the current channel/chat context for new tasks."""
    _current_channel.set(channel)
    _current_chat_id.set(chat_id)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `channel` | `str` | Channel name (e.g. `"telegram"`) |
| `chat_id` | `str` | Chat ID for result delivery |

Uses `contextvars.ContextVar` for async-safe per-task propagation.

### `get_tasks_lock() -> asyncio.Lock`

Return the shared async lock for task file operations. Used by both the cron tools and the `Scheduler` to prevent race conditions.

```python
def get_tasks_lock() -> asyncio.Lock:
    """Return the shared lock for task file operations."""
    if _tasks_lock is None:
        raise RuntimeError("cron tools not initialized - call init_cron_tools() first")
    return _tasks_lock
```

**Raises:** `RuntimeError` if `init_cron_tools()` has not been called.

### `schedule_task(prompt, schedule_type, schedule_value) -> str` {: #schedule-task }

Schedule a task to run later or on a recurring basis.

```python
@tool
async def schedule_task(prompt: str, schedule_type: str, schedule_value: str) -> str:
    """Schedule a task to run later or on a recurring basis.

    Args:
        prompt: What the agent should do when the task runs.
        schedule_type: One of 'cron' (cron expression), 'interval' (seconds), 'once' (ISO timestamp).
        schedule_value: The schedule value matching the type.
    """
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | `str` | What the agent should do when the task runs |
| `schedule_type` | `str` | One of `"cron"`, `"interval"`, `"once"` |
| `schedule_value` | `str` | Value matching the type (cron expression, seconds, or ISO timestamp) |

**Returns:** Confirmation string with task ID, type, and value -- or a validation error message.

**Validation:**

- `schedule_type` must be one of `cron`, `interval`, `once`
- `cron`: validated via `croniter(schedule_value)`
- `interval`: must be a positive integer
- `once`: must be a valid ISO timestamp

**Task JSON structure written to file:**

```json
{
  "id": "abc12345",
  "prompt": "Check the weather",
  "type": "cron",
  "value": "0 9 * * *",
  "channel": "telegram",
  "chat_id": "123456",
  "created_at": "2025-01-15T10:00:00+00:00",
  "last_run": null,
  "active": true
}
```

### `list_tasks() -> str` {: #list-tasks }

List all active scheduled tasks.

```python
@tool
async def list_tasks() -> str:
    """List all active scheduled tasks."""
```

**Returns:** Formatted string with one task per line, or `"No active scheduled tasks."`.

**Output format:**
```
- [abc12345] cron=0 9 * * * | Check the weather | last_run=never
```

### `cancel_task(task_id) -> str` {: #cancel-task }

Cancel a scheduled task by its ID. Sets `active: false` in the tasks JSON file.

```python
@tool
async def cancel_task(task_id: str) -> str:
    """Cancel a scheduled task by its ID."""
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `task_id` | `str` | 8-character UUID prefix |

**Returns:** `"Task {id} cancelled."` or `"Task {id} not found."`.

---

## Host Tools

:octicons-file-code-16: `src/tools/host.py`

### Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_OUTPUT_LENGTH` | `15,000` | Maximum characters returned from command output |

### `init_host_tools(config)`

Initialize host tools with gateway configuration. Creates the `GatewayClient` and builds the bridge-to-commands map.

```python
def init_host_tools(config: GatewayConfig) -> None:
    """Initialize host tools with gateway config."""
    global _gateway_client, _available_bridges, _default_timeout
    if config.url:
        _gateway_client = GatewayClient(config.url, config.token)
    _available_bridges = {
        name: bdef.allowed_commands for name, bdef in config.bridges.items()
    }
    _default_timeout = config.default_timeout
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `config` | `GatewayConfig` | Gateway configuration (URL, token, bridges, timeouts) |

### `host_execute(bridge, command, timeout=0) -> str` {: #host-execute }

Execute a command on the host via the secure gateway.

```python
@tool
async def host_execute(bridge: str, command: str, timeout: int = 0) -> str:
    """Execute a command on the host via the secure gateway.

    Args:
        bridge: Bridge name ("apple-notes", "spotify", "apple-reminders", etc.)
        command: Shell command string (e.g. "memo list", "spogo play 'song name'")
        timeout: Seconds. 0 = use default.
    """
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `bridge` | `str` | *required* | Bridge name (must exist in gateway config) |
| `command` | `str` | *required* | Shell command string (parsed via `shlex.split`) |
| `timeout` | `int` | `0` | Timeout in seconds (0 = use `default_timeout` from config) |

**Returns:** Command stdout, error message, or `"(no output)"`. Truncated at 15,000 characters.

**Error handling:**

- Gateway not configured: `"Error: host gateway not configured."`
- Unknown bridge: `"Error: unknown bridge '{name}'. Available: {list}"`
- Invalid syntax: `"Error: invalid command syntax: {error}"`
- Empty command: `"Error: empty command."`
- Non-zero exit: `"Command failed (exit {code}):\n{stderr}"`
