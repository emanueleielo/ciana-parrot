# Gateway API

::: src.gateway.server
::: src.gateway.client

---

## Overview

The gateway provides secure command execution on the host machine from inside Docker. The server runs on the host and validates requests against per-bridge command allowlists. The client runs inside the container and communicates over HTTP.

**Source files:**

- `src/gateway/server.py` -- HTTP gateway server (runs on host)
- `src/gateway/client.py` -- async HTTP client (runs in container)

---

## Gateway Server

:octicons-file-code-16: `src/gateway/server.py`

The server is a standalone `ThreadingHTTPServer` that validates and executes commands. It is started via `make gateway` or `python -m src.gateway.server`.

### Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_CONTENT_LENGTH` | `1,048,576` (1 MB) | Maximum request body size |
| `MAX_TIMEOUT` | `600` (10 min) | Maximum allowed subprocess timeout |

### Configuration

At startup, the server loads `config.yaml` to build allowlists. Falls back to environment variables if config loading fails:

```python
# Config-driven (normal)
PORT = _cfg.gateway.port            # default: 9842
TOKEN = _cfg.gateway.token          # required for auth
DEFAULT_TIMEOUT = _cfg.gateway.default_timeout

# Env-var fallback
PORT = int(os.environ.get("GATEWAY_PORT", "9842"))
TOKEN = os.environ.get("GATEWAY_TOKEN", "")
```

### `validate_request(data, allowlists)` {: #validate-request }

Validate a request against bridge allowlists. Checks that the bridge exists and the command basename is in the allowlist.

```python
def validate_request(data: dict, allowlists: dict[str, set[str]]) -> tuple[bool, int, str]:
    """Validate a request against bridge allowlists.

    Returns (ok, http_status, error_message). If ok is True, status/message are unused.
    """
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `data` | `dict` | Request JSON with `bridge`, `cmd`, `cwd`, `timeout` |
| `allowlists` | `dict[str, set[str]]` | Map of bridge name to allowed command basenames |

**Returns:** `(ok, http_status, error_message)`

**Validation checks:**

1. `bridge` field must be present
2. `bridge` must exist in allowlists
3. `cmd` must be non-empty
4. Basename of `cmd[0]` must be in the bridge's allowed commands

### `validate_cwd(cwd, bridge, cwd_allowlists)` {: #validate-cwd }

Validate that the working directory is under an allowed path for the bridge.

```python
def validate_cwd(cwd: str | None, bridge: str,
                 cwd_allowlists: dict[str, list[str]]) -> tuple[bool, str]:
    """Validate that cwd is under an allowed directory for the bridge.

    Returns (ok, error_message). If ok is True, error_message is unused.
    """
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `cwd` | `str | None` | Requested working directory |
| `bridge` | `str` | Bridge name |
| `cwd_allowlists` | `dict[str, list[str]]` | Map of bridge to allowed directory prefixes (resolved with `os.path.realpath`) |

**Returns:** `(ok, error_message)`. `cwd=None` always passes.

### `GatewayHandler`

:octicons-file-code-16: `src/gateway/server.py`

HTTP request handler extending `BaseHTTPRequestHandler`. Handles two endpoints:

#### `GET /health`

Returns the gateway status and list of registered bridges.

```json
{
  "status": "ok",
  "bridges": ["claude-code", "apple-notes", "spotify"]
}
```

#### `POST /execute`

Execute a command via a bridge. Requires `Authorization: Bearer <token>` header.

**Request body:**

```json
{
  "bridge": "claude-code",
  "cmd": ["claude", "-p", "--output-format", "stream-json", "Hello"],
  "cwd": "/Users/me/project",
  "timeout": 120
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `bridge` | `str` | Yes | Bridge name |
| `cmd` | `list[str]` | Yes | Command as list of strings |
| `cwd` | `str` | No | Working directory on host |
| `timeout` | `int` | No | Subprocess timeout (0 = no limit, clamped to `MAX_TIMEOUT`) |

**Response:**

```json
{
  "stdout": "...",
  "stderr": "...",
  "returncode": 0
}
```

**Error responses:**

| Status | Condition |
|--------|-----------|
| `400` | Missing/invalid JSON, missing `bridge` or `cmd` |
| `401` | Invalid or missing auth token |
| `403` | Bridge not in allowlists, command not allowed, or cwd not under allowed directory |
| `413` | Request body exceeds `MAX_CONTENT_LENGTH` |
| `500` | Subprocess execution error |

**Special cases:**

- `FileNotFoundError` returns `returncode: 127` with a descriptive `stderr` message
- `TimeoutExpired` returns `returncode: -1` with `"Command timed out"` in `stderr`

---

## Gateway Client

### `GatewayResult`

:octicons-file-code-16: `src/gateway/client.py`

Dataclass representing the result of a gateway command execution.

```python
@dataclass
class GatewayResult:
    """Result from a gateway command execution."""
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    error: str = ""
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `stdout` | `str` | `""` | Standard output from the command |
| `stderr` | `str` | `""` | Standard error from the command |
| `returncode` | `int` | `0` | Process exit code |
| `error` | `str` | `""` | Client-side error message (connection failure, timeout, etc.) |

### `GatewayClient`

:octicons-file-code-16: `src/gateway/client.py`

Async HTTP client for communicating with the host gateway server. Uses `httpx.AsyncClient` for non-blocking requests.

#### Constructor

```python
class GatewayClient:
    def __init__(self, base_url: str, token: Optional[str] = None):
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | *required* | Gateway URL (e.g. `"http://host.docker.internal:9842"`) |
| `token` | `Optional[str]` | `None` | Bearer token for authentication |

#### `execute(bridge, cmd, cwd=None, timeout=0) -> GatewayResult` {: #client-execute }

Execute a command via the gateway.

```python
async def execute(
    self,
    bridge: str,
    cmd: list[str],
    cwd: Optional[str] = None,
    timeout: int = 0,
) -> GatewayResult:
    """Execute a command via the gateway.

    Args:
        bridge: Bridge name (e.g. "claude-code", "apple-notes").
        cmd: Command as list of strings.
        cwd: Working directory on the host.
        timeout: Subprocess timeout in seconds. 0 = no timeout.
    """
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `bridge` | `str` | *required* | Bridge name |
| `cmd` | `list[str]` | *required* | Command as list of strings |
| `cwd` | `Optional[str]` | `None` | Working directory on host |
| `timeout` | `int` | `0` | Subprocess timeout (0 = no limit) |

**Returns:** `GatewayResult` with stdout/stderr/returncode, or `error` on failure.

**HTTP timeout logic:** If `timeout=0`, the HTTP client uses no timeout (`None`). Otherwise, it adds a 10-second buffer: `timeout + 10`.

**Error handling:**

- `httpx.ConnectError` -- returns error about gateway not running
- `httpx.TimeoutException` -- returns timeout error
- HTTP 401 -- returns auth failure error
- HTTP 403 -- returns the server's error message

#### `health() -> tuple[bool, dict]` {: #client-health }

Check gateway health.

```python
async def health(self) -> tuple[bool, dict]:
    """Check gateway health. Returns (ok, response_data)."""
```

**Returns:** `(True, {"status": "ok", "bridges": [...]})` or `(False, {"error": "..."})`.
