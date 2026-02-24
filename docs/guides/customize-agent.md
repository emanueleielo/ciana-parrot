---
title: Customize the Agent
---

# Customize the Agent

CianaParrot's AI agent is built on **DeepAgents** with LangChain/LangGraph. This guide covers every customization point.

## LLM Provider

Change the provider and model in `config.yaml`:

```yaml
provider:
  name: "anthropic"          # anthropic | openai | openrouter | ollama | vllm | groq | google-genai
  model: "claude-sonnet-4-6"
  api_key: "${ANTHROPIC_API_KEY}"
  temperature: 0
  max_tokens: 8192
```

The agent uses `init_chat_model("{provider}:{model}")` from LangChain, so any provider supported by LangChain works.

For self-hosted models:

```yaml
provider:
  name: "ollama"
  model: "llama3"
  base_url: "http://localhost:11434"
```

For OpenRouter:

```yaml
provider:
  name: "openrouter"
  model: "anthropic/claude-sonnet-4-6"
  api_key: "${OPENROUTER_API_KEY}"
  base_url: "https://openrouter.ai/api/v1"
```

## Memory Files

Place these files in `workspace/` to customize the agent's personality and knowledge:

| File | Purpose |
|------|---------|
| `IDENTITY.md` | Who the agent is — name, personality, communication style |
| `AGENT.md` | Capabilities, instructions, behavioral guidelines |
| `MEMORY.md` | Persistent memory — the agent reads and writes this across sessions |

All three are loaded as system context automatically if they exist:

```python
# src/agent.py
for fname in ["IDENTITY.md", "AGENT.md", "MEMORY.md"]:
    fpath = Path(workspace, fname)
    if fpath.exists():
        memory_files.append(fname)
```

!!! tip
    `MEMORY.md` is special — the agent can update it during conversations to remember things. Protect it from accidental commits with `git update-index --skip-worktree workspace/MEMORY.md`.

## Tool Iterations

Control how many tool calls the agent can make per turn:

```yaml
agent:
  max_tool_iterations: 20  # default
```

Increase for complex multi-step tasks, decrease to keep responses faster.

## MCP Servers

Add external tool servers via the [Model Context Protocol](https://modelcontextprotocol.io/):

```yaml
mcp_servers:
  filesystem:
    transport: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]

  weather:
    transport: "sse"
    url: "http://localhost:3001/sse"
```

Tools from MCP servers are loaded via `MultiServerMCPClient` and merged with custom tools:

```python
all_tools = custom_tools + mcp_tools
```

## Custom Tools

Add tools to the agent by following the [Add a Tool](add-tool.md) guide. The built-in tools are:

| Tool | Module | Description |
|------|--------|-------------|
| `web_search` | `src/tools/web.py` | Search via Brave or DuckDuckGo |
| `web_fetch` | `src/tools/web.py` | Fetch URL content as markdown |
| `schedule_task` | `src/tools/cron.py` | Schedule a task |
| `list_tasks` | `src/tools/cron.py` | List active scheduled tasks |
| `cancel_task` | `src/tools/cron.py` | Cancel a scheduled task |
| `host_execute` | `src/tools/host.py` | Run commands on host via gateway |

## Backend and Sandboxing

The agent's filesystem access is managed by `WorkspaceShellBackend`:

```python
agent = create_deep_agent(
    model=model,
    backend=WorkspaceShellBackend(root_dir=workspace, virtual_mode=True),
    # ...
)
```

With `virtual_mode=True`, the agent is confined to the `workspace/` directory for all file operations (`read_file`, `write_file`, `edit_file`, `ls`, `glob`, `grep`).

### Shell Commands

The backend also provides an `execute` tool with an allowlisted set of commands:

```
curl, wget, python, python3, pip, pip3, git, jq, ffmpeg, ffprobe,
echo, date, env, whoami, tar, gzip, gunzip, unzip, wc, sort, uniq,
tr, cut, base64, sha256sum, md5sum
```

Shell metacharacters (`;|&`$`) are rejected to prevent command chaining.

## Host Filesystem Access

To give the agent access to host directories, mount them in `docker-compose.yml`:

```yaml
volumes:
  - ./workspace:/app/workspace
  - ~/Documents:/app/workspace/host/documents:ro    # read-only
  - ~/Projects:/app/workspace/host/projects         # read-write
```

The agent accesses them as `host/documents/...` using its existing filesystem tools.

!!! warning
    Use `:ro` (read-only) by default. Only grant write access when necessary.

## Skills

Enable the skills system to let the agent discover and use task-specific tools:

```yaml
skills:
  enabled: true
  directory: "skills"  # relative to workspace
```

See [Add a Skill](add-skill.md) for creating custom skills.
