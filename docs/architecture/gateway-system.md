# Gateway System

The gateway bridges the Docker container to host-side CLI tools through a secure HTTP server. It enforces per-bridge command allowlists, directory restrictions, and HMAC token authentication.

## Architecture

```mermaid
graph LR
    subgraph Docker["Docker Container"]
        HT[host_execute tool]
        GC[GatewayClient]
        CCB[ClaudeCodeBridge]
    end

    subgraph Host["Host Machine"]
        GS[Gateway Server :9842]

        subgraph Allowlists["Bridge Allowlists"]
            B1[claude-code]
            B2[spotify]
            B3[apple-reminders]
            B4[apple-notes]
        end

        SP[subprocess.run]
        CLI[Host CLI Tools]
    end

    HT -->|shlex.split| GC
    GC -->|POST /execute| GS
    CCB -->|POST /execute| GS
    GS -->|validate| B1
    GS -->|validate| B2
    GS -->|validate| B3
    GS -->|validate| B4
    GS --> SP
    SP --> CLI
```

## Gateway Server

**File**: `src/gateway/server.py`

The gateway runs on the host machine as a standalone Python process (`make gateway` or `python -m src.gateway.server`). It uses Python's `ThreadingHTTPServer` for simplicity.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Returns `{"status": "ok", "bridges": [...]}` with the list of configured bridge names |
| `POST` | `/execute` | Validates and executes a command. Returns `{"stdout": ..., "stderr": ..., "returncode": ...}` |

### Request Format

```json
{
    "bridge": "claude-code",
    "cmd": ["claude", "-p", "--output-format", "stream-json", "hello"],
    "cwd": "/Users/me/Projects/myapp",
    "timeout": 120
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `bridge` | string | Yes | Bridge name matching a key in `config.gateway.bridges` |
| `cmd` | list[string] | Yes | Command as a list of arguments (not a shell string) |
| `cwd` | string | No | Working directory on the host. Validated against bridge's `allowed_cwd` |
| `timeout` | number | No | Subprocess timeout in seconds. `0` = no limit (None). Capped at 600s |

### Response Format

**Success (200)**:
```json
{
    "stdout": "command output here",
    "stderr": "",
    "returncode": 0
}
```

**Command not found (200, returncode 127)**:
```json
{
    "stdout": "",
    "stderr": "Command 'claude' not found on host. Install it first.",
    "returncode": 127
}
```

**Timeout (200, returncode -1)**:
```json
{
    "stdout": "",
    "stderr": "Command timed out",
    "returncode": -1
}
```

**Validation errors**: HTTP 400 (bad request), 401 (auth), 403 (forbidden), 413 (body too large), 500 (server error).

### Request Validation Flow

```mermaid
flowchart TD
    A[POST /execute] --> B{HMAC auth check}
    B -->|Fail| C[401 Unauthorized]
    B -->|Pass| D{Content-Length OK?}
    D -->|No| E[413 Too Large]
    D -->|Yes| F[Parse JSON body]
    F -->|Invalid| G[400 Bad Request]
    F -->|Valid| H{Bridge exists?}
    H -->|No| I[403 Unknown bridge]
    H -->|Yes| J{Command in allowlist?}
    J -->|No| K[403 Command not allowed]
    J -->|Yes| L{CWD provided?}
    L -->|No| M[Skip CWD check]
    L -->|Yes| N{CWD under allowed_cwd?}
    N -->|No| O[403 CWD not allowed]
    N -->|Yes| M
    M --> P[Clamp timeout]
    P --> Q[subprocess.run]
    Q --> R{Result?}
    R -->|Success| S[200 + stdout/stderr/rc]
    R -->|FileNotFoundError| T[200 + rc=127]
    R -->|TimeoutExpired| U[200 + rc=-1]
    R -->|Other error| V[500]
```

## Security Model

```mermaid
flowchart LR
    subgraph L1["1. Authentication"]
        TOKEN[HMAC Token]
    end

    subgraph L2["2. Bridge Validation"]
        BRIDGE[Bridge must exist in config]
    end

    subgraph L3["3. Command Allowlist"]
        CMD[Basename must be allowed]
    end

    subgraph L4["4. CWD Restriction"]
        CWD[Realpath under allowed dirs]
    end

    subgraph L5["5. Resource Limits"]
        LIMITS[Size + timeout + no shell]
    end

    TOKEN --> BRIDGE --> CMD --> CWD --> LIMITS
```

- **HMAC token authentication**: The `GATEWAY_TOKEN` environment variable is required. Comparison uses `hmac.compare_digest()` to prevent timing attacks. The server refuses to start if no token is set.
- **Command basename validation**: Only the basename of `cmd[0]` is checked (via `os.path.basename()`), preventing path-based bypass attempts like `/usr/bin/../bin/dangerous`.
- **CWD path traversal prevention**: The `cwd` parameter is resolved to its real path (via `os.path.realpath()`) and must be equal to or a subdirectory of one of the bridge's `allowed_cwd` entries. This prevents symlink and `../` traversal attacks.
- **Content length limit**: Request bodies larger than 1 MB (`MAX_CONTENT_LENGTH = 1_048_576`) are rejected.
- **Timeout capping**: Timeouts are clamped to `MAX_TIMEOUT = 600` seconds. A timeout of 0 means no limit (subprocess runs until completion).
- **No shell execution**: Commands are executed via `subprocess.run()` with `shell=False` and a command list, preventing shell injection.
- **Environment sanitization**: `CLAUDE_CODE` and `CLAUDECODE` environment variables are removed before subprocess execution to prevent recursive Claude Code invocations.

## Gateway Client

**File**: `src/gateway/client.py`

The `GatewayClient` is an async HTTP client used inside the Docker container to communicate with the gateway server.

```python
@dataclass
class GatewayResult:
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    error: str = ""
```

### Error Handling

| Scenario | Behavior |
|----------|----------|
| `httpx.ConnectError` | Returns `GatewayResult(error="Cannot connect to host gateway...")` |
| `httpx.TimeoutException` | Returns `GatewayResult(error="Gateway request timed out.")` |
| HTTP 401 | Returns `GatewayResult(error="Gateway auth failed. Check GATEWAY_TOKEN.")` |
| HTTP 403 | Returns `GatewayResult(error=<server error message>)` |
| Other HTTP errors | Returns `GatewayResult(error="Gateway returned HTTP {status}")` |

### HTTP Timeout Behavior

The HTTP client timeout is calculated based on the subprocess timeout:

- **timeout = 0** (no subprocess limit): HTTP timeout = `None` (no limit)
- **timeout > 0**: HTTP timeout = `timeout + 10` seconds (buffer for network overhead)

## host_execute Tool

**File**: `src/tools/host.py`

The `host_execute` tool is the LangChain `@tool` that the agent calls to run commands on the host. It acts as the front-end to `GatewayClient`.

```mermaid
flowchart TD
    A[Agent calls host_execute] --> B{Gateway configured?}
    B -->|No| C[Error: not configured]
    B -->|Yes| D{Bridge name valid?}
    D -->|No| E[Error: unknown bridge]
    D -->|Yes| F[shlex.split command]
    F -->|Invalid| G[Error: invalid syntax]
    F -->|Valid| H[GatewayClient.execute]
    H --> I{GatewayResult}
    I -->|error set| J[Return error]
    I -->|returncode != 0| K[Command failed]
    I -->|success| L[Return stdout]
    L --> M{Length > 15000?}
    M -->|Yes| N[Truncate + "... (truncated)"]
    M -->|No| O[Return as-is]
```

The tool takes a shell command string (not a list), parses it with `shlex.split()`, and validates the bridge name against `_available_bridges` before sending. Output is capped at `MAX_OUTPUT_LENGTH = 15_000` characters. If no timeout is specified (or timeout=0), it uses `_default_timeout` from the gateway config.

## Claude Code Bridge

**File**: `src/gateway/bridges/claude_code/bridge.py`

The `ClaudeCodeBridge` is a specialized bridge that manages Claude Code CLI interactions with per-user state.

### Per-User State

```python
@dataclass
class UserSession:
    mode: str = "ciana"                          # "ciana" or "claude_code"
    active_project: str | None = None            # Encoded project directory name
    active_project_path: str | None = None       # Real filesystem path
    active_session_id: str | None = None         # Claude Code session ID (UUID)
    active_model: str | None = None              # Model override (e.g., "sonnet")
    active_effort: str | None = None             # Effort level: low/medium/high
```

State is persisted in `data/cc_user_states.json` via `JsonStore` and restored on startup.

### Command Construction

```mermaid
flowchart TD
    A[send_message] --> B[_build_command]
    B --> C[claude -p]
    C --> D{Session ID?}
    D -->|Yes| E[--resume session_id]
    D -->|No| F[Skip]
    E --> G{Fork?}
    G -->|Yes| H[--fork-session]
    G -->|No| I[Continue]
    H --> I
    F --> I
    I --> J[--output-format stream-json]
    J --> K{Permission mode?}
    K -->|Set| L[--permission-mode]
    K -->|None| M[Skip]
    L --> N{Model override?}
    M --> N
    N -->|Set| O[--model]
    N -->|None| P[Skip]
    O --> Q{Effort?}
    P --> Q
    Q -->|Set| R[--effort]
    Q -->|None| S[Skip]
    R --> T[Append message text]
    S --> T
```

### Execution Modes

The bridge supports two execution modes:

1. **Via gateway** (`_execute_via_bridge`): Sends the command through the HTTP gateway. Used when running in Docker.
2. **Local** (`_execute_local`): Runs the Claude Code CLI directly via `asyncio.create_subprocess_exec()`. Used for local development.

The mode is determined by whether `bridge_url` is configured.

### NDJSON Response Parsing

```mermaid
flowchart TD
    A[Raw stdout from claude CLI] --> B[Split into lines]
    B --> C[Parse each line as JSON]
    C --> D[Iterate parsed objects]
    D --> E{type field?}
    E -->|"result"| F[Skip]
    E -->|Other| G[Iterate content blocks]
    G --> H{Block type?}
    H -->|tool_use| I[ToolCallEvent]
    H -->|tool_result| J[Pair with tool_use]
    H -->|text| K[TextEvent]
    H -->|thinking| L[ThinkingEvent]
    I --> M[_build_response]
    J --> M
    K --> M
    L --> M
    M --> N[Pair tool calls with results]
    N --> O[CCResponse]
```

The bridge parses Claude Code's NDJSON (stream-json) output into structured events:

- **TextEvent**: Plain text assistant response
- **ToolCallEvent**: Tool invocation with input summary and result text, paired by `tool_use_id`
- **ThinkingEvent**: Extended thinking block content

These events are shared types (defined in `src/events.py`) used by both the normal agent response extraction and the Claude Code bridge, enabling a unified rendering pipeline in the Telegram channel.

### Project and Conversation Discovery

The bridge scans `~/.claude/projects/` (configurable via `claude_code.projects_dir`) to discover projects and conversations:

```mermaid
flowchart TD
    A[projects directory] --> B[Iterate subdirectories]
    B --> C[For each project dir]
    C --> D[Find *.jsonl files]
    D --> E[Peek first line for cwd]
    E --> F[ProjectInfo]
    D --> G[Parse each JSONL file]
    G --> H[Extract metadata]
    H --> I[ConversationInfo]
```

**ProjectInfo** is derived from the directory structure. The `real_path` is extracted by reading the `cwd` field from the first line of the most recent JSONL file.

**ConversationInfo** is parsed from each JSONL session file, extracting the first user message as a preview, the timestamp, message count, and git branch metadata.

### New Session Detection

When a user starts a new conversation (no `active_session_id`), the bridge snapshots existing session files before executing the command. After execution, it compares the directory listing to find the newly created JSONL file and records its stem as the `active_session_id`. This is persisted so subsequent messages resume the same session.

## Configuration

Bridge configuration lives in `config.yaml` under the `gateway` section:

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
      allowed_cwd: ["~/Projects", "~/Documents"]
    spotify:
      allowed_commands: ["spogo"]
      allowed_cwd: []
    apple-reminders:
      allowed_commands: ["reminders"]
      allowed_cwd: []
    apple-notes:
      allowed_commands: ["memo"]
      allowed_cwd: []
```

The `BridgeDefinition` Pydantic model validates each bridge:

```python
class BridgeDefinition(BaseModel):
    allowed_commands: list[str] = Field(default_factory=list)
    allowed_cwd: list[str] = Field(default_factory=list)
```

The Claude Code bridge has additional configuration under `claude_code`:

```yaml
claude_code:
  enabled: true
  bridge_url: ""          # Falls back to gateway.url
  bridge_token: ""        # Falls back to gateway.token
  projects_dir: "~/.claude/projects"
  permission_mode: ""     # e.g., "bypassPermissions"
  timeout: 0              # 0 = no limit
  claude_path: "claude"   # Path to claude CLI
  state_file: "data/cc_user_states.json"
```
