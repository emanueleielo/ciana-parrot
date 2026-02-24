---
title: Skill Format
---

# Skill Format Reference

Skills are the primary extension mechanism in CianaParrot. A skill is a self-contained directory that teaches the agent new capabilities -- from controlling Spotify to generating images to managing Notion pages. Skills are loaded automatically at startup via the DeepAgents framework.

---

## Directory Structure

Each skill lives in its own subdirectory under the skills directory (default: `workspace/skills/`):

```
workspace/skills/my-skill/
  SKILL.md        # Required — Skill metadata + agent instructions
  skill.py        # Optional — Python tool implementations
```

| File | Required | Purpose |
|------|----------|---------|
| `SKILL.md` | Yes | YAML frontmatter (metadata) + Markdown body (agent instructions) |
| `skill.py` | No | Python functions decorated with `@tool` that auto-register as agent tools |

!!! tip "Skills without `skill.py`"
    Many skills only need a `SKILL.md`. If the skill works by instructing the agent to use existing tools (like `host_execute` for bridge commands, or shell commands via `web_fetch`), no Python code is needed. The Markdown body provides all the context the agent needs.

---

## SKILL.md Format

The file consists of **YAML frontmatter** (between `---` delimiters) followed by a **Markdown body**.

### Frontmatter Fields

```yaml title="SKILL.md frontmatter"
---
name: my-skill                              # (1)!
description: "Brief description of the skill"  # (2)!
requires_env:                               # (3)!
  - API_KEY_NAME
requires_bridge: "bridge-name"              # (4)!
homepage: https://example.com               # (5)!
metadata:                                   # (6)!
  openclaw:
    emoji: "\U0001f3b5"
    requires:
      bins: ["curl"]
---
```

1. **`name`** (`str`, required) -- Unique skill identifier. By convention, matches the directory name.
2. **`description`** (`str`, required) -- Short description shown to the agent when deciding which skills to use. Keep it actionable: describe _when_ to use the skill, not just what it does.
3. **`requires_env`** (`str | list[str]`, optional) -- Environment variable(s) that must be set for this skill to load. If any are missing, the skill is silently skipped at startup.
4. **`requires_bridge`** (`str | list[str]`, optional) -- Gateway bridge(s) that must be configured in `gateway.bridges` for this skill to load. If any are missing, the skill is silently skipped.
5. **`homepage`** (`str`, optional) -- URL to the upstream tool or service documentation. Informational only.
6. **`metadata`** (`dict`, optional) -- Arbitrary metadata. Used by OpenClaw for skill registry display (emoji, binary requirements). Not processed by CianaParrot directly.

### Frontmatter Field Reference

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | `str` | Yes | -- | Unique skill identifier |
| `description` | `str` | Yes | -- | Brief description for the agent |
| `requires_env` | `str` or `list[str]` | No | -- | Env vars that must be set |
| `requires_bridge` | `str` or `list[str]` | No | -- | Bridges that must be configured |
| `homepage` | `str` | No | -- | Upstream documentation URL |
| `metadata` | `dict` | No | -- | Arbitrary metadata (OpenClaw, etc.) |

### Markdown Body

The body after the frontmatter closing `---` is loaded as context for the agent. This is where you provide detailed instructions, command references, examples, and troubleshooting guidance.

**Recommended structure:**

```markdown
# Skill Name

Brief overview.

## When to Use

- Scenario 1
- Scenario 2

## When NOT to Use

- Anti-pattern 1
- Anti-pattern 2

## Commands

Detailed command reference with examples.

## Known Issues & Workarounds

Common failure modes and how to handle them.

## Troubleshooting

Step-by-step diagnostic flow.
```

---

## Complete SKILL.md Examples

### Bridge Skill (no Python)

A skill that instructs the agent to use `host_execute` with a specific bridge:

```markdown title="skills/spotify/SKILL.md"
---
name: spotify
description: "Control Spotify playback: play, pause, skip, search tracks/albums/playlists, manage devices and queue via spogo CLI."
requires_bridge: "spotify"
---

# Spotify

Use the `spotify` bridge to control Spotify playback via `spogo` on the host.

## When to Use

- User asks to play, pause, skip music
- Searching for songs, albums, artists, playlists
- Managing playback devices or queue

## Commands

All commands run via `host_execute(bridge="spotify", command="...")`.

### Playback

    spogo status --json          # What's playing
    spogo play <uri>             # Play a specific URI
    spogo pause                  # Pause
    spogo next                   # Next track
```

### Env-Gated Skill (with Python tools)

A skill that requires an API key and provides custom Python tools:

```markdown title="skills/openai-image-gen/SKILL.md"
---
name: openai-image-gen
description: "Generate images with DALL-E 3 via OpenAI API. Use when user asks to create or generate images. Requires OPENAI_API_KEY."
requires_env:
  - OPENAI_API_KEY
---

# OpenAI Image Generation

Generate images using DALL-E 3.

## When to Use

- User asks to create, generate, or draw an image
- Visual content creation requests
```

### Standalone Skill (no requirements)

A skill with no bridge or env dependencies:

```markdown title="skills/weather/SKILL.md"
---
name: weather
description: "Get current weather and forecasts via wttr.in or Open-Meteo. Use when: user asks about weather, temperature, or forecasts for any location. No API key needed."
---

# Weather Skill

Get current weather conditions and forecasts.

## Commands

    curl "wttr.in/London?format=3"     # One-line summary
    curl "wttr.in/London?format=j1"    # JSON output
```

---

## skill.py Format

Optional Python file that provides custom tools. Functions decorated with `@tool` from `langchain_core.tools` are automatically discovered and registered as agent-callable tools by DeepAgents.

### Synchronous Tool

```python title="skill.py"
from langchain_core.tools import tool


@tool
def my_action(param: str) -> str:
    """Description shown to the agent when choosing tools.

    Args:
        param: What this parameter controls.
    """
    return f"Result for {param}"
```

### Async Tool

```python title="skill.py"
import httpx
from langchain_core.tools import tool


@tool
async def fetch_data(url: str) -> str:
    """Fetch data from a URL and return the response body.

    Args:
        url: The URL to fetch.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text
```

### Tool Conventions

| Convention | Details |
|------------|---------|
| **Docstring** | Required. First line is the tool description shown to the agent. `Args:` section documents parameters. |
| **Type hints** | Required on all parameters and return type. The agent uses these to construct valid calls. |
| **Return type** | Should be `str`. The agent receives the return value as a text response. |
| **Error handling** | Return error messages as strings rather than raising exceptions. The agent can interpret error text. |
| **Imports** | Keep imports inside the function if they're optional dependencies. Top-level imports for standard libraries. |

---

## Middleware Filtering

CianaParrot patches the DeepAgents skill parser (`src/middleware.py`) to add two filtering mechanisms that control which skills are loaded at startup.

### `requires_env` Filtering

Skills declare environment variable dependencies in their frontmatter:

```yaml
requires_env:
  - OPENAI_API_KEY
  - ANOTHER_KEY
```

At startup, the middleware checks each listed variable via `os.environ.get()`. If **any** variable is missing or empty, the skill is silently skipped and a `DEBUG`-level log message is emitted.

**Supports both formats:**

```yaml
# Single string
requires_env: "API_KEY"

# List of strings
requires_env:
  - API_KEY_1
  - API_KEY_2
```

### `requires_bridge` Filtering

Skills declare gateway bridge dependencies:

```yaml
requires_bridge: "spotify"
```

At startup, `init_middleware_bridges()` reads the configured bridge names from `gateway.bridges` in `config.yaml`. Skills whose required bridges are not in this set are silently skipped.

**Supports both formats:**

```yaml
# Single string
requires_bridge: "spotify"

# List of strings (all must be present)
requires_bridge:
  - "spotify"
  - "sonos"
```

### Auto-Fix for Unquoted YAML

The middleware includes a fallback parser that automatically quotes unquoted YAML values that contain colons (a common frontmatter authoring mistake). If the original DeepAgents parser fails, the middleware retries with auto-quoted values and logs an `INFO` message.

---

## Loading Order

1. **Startup**: `create_cianaparrot_agent()` initializes the agent with the skills directory
2. **Discovery**: DeepAgents scans all subdirectories of `workspace/skills/`
3. **Frontmatter parsing**: Each `SKILL.md` is parsed; the middleware intercepts this step
4. **Filtering**: `requires_env` and `requires_bridge` checks are applied
5. **Registration**: Surviving skills have their `SKILL.md` body loaded as agent context and any `skill.py` tools registered

---

## Source

- Skill loading: DeepAgents framework (`deepagents.middleware.skills`)
- Middleware patches: [`src/middleware.py`](https://github.com/emanueleielo/ciana-parrot/blob/main/src/middleware.py)
- Skills directory: `workspace/skills/` (configurable via `skills.directory`)
