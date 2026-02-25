---
title: Agent API
---

# Agent API

**Module:** `src/agent.py`

## create_cianaparrot_agent

```python
async def create_cianaparrot_agent(config: AppConfig) -> tuple[agent, checkpointer, mcp_client]
```

Factory function that builds the complete agent with all tools, memory, and persistence.

### Returns

| Index | Type | Description |
|-------|------|-------------|
| `agent` | LangGraph `CompiledGraph` | The runnable agent |
| `checkpointer` | `AsyncSqliteSaver` | LangGraph conversation persistence |
| `mcp_client` | `MultiServerMCPClient \| None` | MCP client (if configured), needs cleanup on shutdown |

### Construction Sequence

1. **Initialize tool configs** — calls `init_web_tools()`, `init_cron_tools()`, `init_host_tools()` (if gateway enabled), `init_transcription()` (if enabled)
2. **Create base LLM** — `init_chat_model("{provider}:{model}")` with optional temperature, max_tokens, base_url
3. **Model router** (if `model_router.enabled`) — initializes all tier models, creates `RoutingChatModel` as the main model (replaces `provider`), adds `switch_model` tool. Each tier is pre-bound with tools via `bind_tools()`.
4. **Load memory files** — scans workspace for `IDENTITY.md`, `AGENT.md`, `MEMORY.md`
5. **Load MCP tools** — `MultiServerMCPClient(config.mcp_servers)` if configured
6. **Build tool list** — `[web_search, web_fetch, schedule_task, list_tasks, cancel_task]` + optionally `host_execute` + optionally `switch_model`
7. **Create checkpointer** — `AsyncSqliteSaver` backed by `data/checkpoints.db`
8. **Create agent** — `create_deep_agent()` with `WorkspaceShellBackend`

### Usage

```python
agent, checkpointer, mcp_client = await create_cianaparrot_agent(config)

# Invoke the agent
result = await agent.ainvoke(
    {"messages": [{"role": "user", "content": "Hello"}]},
    config={"configurable": {"thread_id": "telegram_12345"}},
)
```

---

## WorkspaceShellBackend

**Module:** `src/backend.py`

```python
class WorkspaceShellBackend(SandboxBackendProtocol, FilesystemBackend):
    def __init__(self, *, root_dir, virtual_mode=True, timeout=120, max_output_bytes=100_000): ...
```

Combines DeepAgents' `FilesystemBackend` (sandboxed file tools) with an allowlisted shell executor.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `root_dir` | `str` | — | Workspace directory path |
| `virtual_mode` | `bool` | `True` | Confine file operations to `root_dir` |
| `timeout` | `int` | `120` | Shell command timeout in seconds |
| `max_output_bytes` | `int` | `100_000` | Max output before truncation |

### File Tools (from FilesystemBackend)

With `virtual_mode=True`, these tools are sandboxed to the workspace:

- `ls` — list directory contents
- `read_file` — read file contents
- `write_file` — create or overwrite a file
- `edit_file` — apply edits to a file
- `glob` — pattern matching
- `grep` — content search

### Shell Execution

```python
def execute(self, command: str) -> ExecuteResponse: ...
async def aexecute(self, command: str) -> ExecuteResponse: ...
```

**Allowed commands** (26 total):

```
curl, wget, python, python3, pip, pip3, git, jq, ffmpeg, ffprobe,
nano-pdf, echo, date, env, whoami, tar, gzip, gunzip, unzip,
wc, sort, uniq, tr, cut, base64, sha256sum, md5sum
```

**Security:**

- Command basename must be in `ALLOWED_COMMANDS`
- Shell metacharacters (`;|&`$`) are rejected before parsing
- Executed via `subprocess.run(shell=False)` — no shell injection
- Output truncated at `max_output_bytes`

### ExecuteResponse

```python
@dataclass
class ExecuteResponse:
    output: str
    exit_code: int
    truncated: bool = False
```
