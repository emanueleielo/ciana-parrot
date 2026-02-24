---
title: Add a Skill
---

# Add a Skill

This guide shows you how to create a skill -- a self-contained package of tools that the agent discovers automatically at startup.

---

## Introduction

Skills are the easiest way to extend CianaParrot. A skill is a folder inside `workspace/skills/` containing two files:

- **`SKILL.md`** -- a markdown file with YAML frontmatter that describes the skill to the agent
- **`skill.py`** -- a Python file with `@tool`-decorated functions that auto-register as agent tools

DeepAgents discovers skills at startup by scanning the skills directory. The agent receives the skill description as context and can call the skill's tools during conversations.

---

## Prerequisites

- A working CianaParrot installation ([Installation Guide](../getting-started/installation.md))
- The skills system enabled in config (default: `skills.enabled: true`)
- Basic familiarity with LangChain's `@tool` decorator

---

## Step 1: Create the Skill Directory

```bash
mkdir -p workspace/skills/my-skill
```

!!! note "Path inside Docker"
    The `workspace/` directory is mounted into the container at `/app/workspace`. The agent sees skills at the virtual path `skills/my-skill/` relative to the workspace root.

---

## Step 2: Write the Skill Description

Create `SKILL.md` with YAML frontmatter:

```markdown title="workspace/skills/my-skill/SKILL.md"
---
name: My Skill
description: Provides tools for managing grocery lists
---

# My Skill

This skill helps manage grocery lists. Use it when the user asks about
shopping, groceries, or meal planning.

## Available Tools

- `add_grocery_item` -- Add an item to the grocery list
- `list_groceries` -- Show the current grocery list
- `clear_groceries` -- Clear the grocery list
```

The YAML frontmatter fields:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Display name for the skill |
| `description` | Yes | Short description shown to the agent |
| `requires_env` | No | Environment variable(s) that must be set |
| `requires_bridge` | No | Bridge(s) that must be configured in the gateway |

---

## Step 3: Implement the Tool Functions

Create `skill.py` with `@tool`-decorated functions:

```python title="workspace/skills/my-skill/skill.py"
"""Grocery list skill."""

import json
from pathlib import Path
from langchain_core.tools import tool

# Skills run inside the agent's workspace sandbox.
# Use a path relative to the skill directory for data storage.
_DATA_FILE = Path(__file__).parent / "groceries.json"


def _load() -> list[str]:
    if _DATA_FILE.exists():
        return json.loads(_DATA_FILE.read_text())
    return []


def _save(items: list[str]) -> None:
    _DATA_FILE.write_text(json.dumps(items, indent=2))


@tool
def add_grocery_item(item: str) -> str:
    """Add an item to the grocery list.

    Args:
        item: The grocery item to add (e.g. "milk", "2 avocados").
    """
    items = _load()
    items.append(item)
    _save(items)
    return f"Added '{item}'. List now has {len(items)} item(s)."


@tool
def list_groceries() -> str:
    """Show all items currently on the grocery list."""
    items = _load()
    if not items:
        return "The grocery list is empty."
    numbered = [f"{i+1}. {item}" for i, item in enumerate(items)]
    return "Grocery list:\n" + "\n".join(numbered)


@tool
def clear_groceries() -> str:
    """Clear all items from the grocery list."""
    _save([])
    return "Grocery list cleared."
```

!!! tip "Tool docstrings matter"
    The agent sees the function name, docstring, and parameter annotations. Write clear, specific docstrings so the agent knows when and how to use each tool.

---

## Step 4: (Optional) Add Conditional Requirements

### Require an environment variable

If your skill needs an API key, declare it in the frontmatter:

```yaml title="workspace/skills/my-skill/SKILL.md (frontmatter)"
---
name: My Skill
description: Provides tools for managing grocery lists
requires_env: "GROCERY_API_KEY"
---
```

If `GROCERY_API_KEY` is not set in the environment, the skill is silently skipped at startup. You can also require multiple variables:

```yaml
requires_env:
  - "GROCERY_API_KEY"
  - "GROCERY_STORE_ID"
```

### Require a gateway bridge

If your skill depends on a host bridge:

```yaml title="workspace/skills/my-skill/SKILL.md (frontmatter)"
---
name: My Skill
description: Controls the smart fridge via host bridge
requires_bridge: "smart-fridge"
---
```

The middleware (`src/middleware.py`) checks bridge availability at startup and filters out skills whose bridges are not configured in `gateway.bridges`.

---

## Step 5: Verify Discovery

Restart the container to trigger skill discovery:

```bash
make restart
```

Check the logs for confirmation:

```bash
make logs
```

You should see output similar to:

```
Skills directory: /app/workspace/skills (workspace-relative)
```

!!! note "No registration code needed"
    Unlike tools (which require manual wiring in `agent.py`), skills are auto-discovered by DeepAgents from the `workspace/skills/` directory. Just drop the folder in place and restart.

---

## Step 6: Test It

### Manual test via Telegram

Send a message to the bot:

> Add milk, eggs, and bread to my grocery list

The agent should recognize the intent, call `add_grocery_item` three times, and confirm each addition.

### Unit test

```python title="tests/test_grocery_skill.py"
import sys
from pathlib import Path

# Add the skill directory to the path for direct import
sys.path.insert(0, str(Path("workspace/skills/my-skill")))

from skill import add_grocery_item, list_groceries, clear_groceries


def test_add_and_list(tmp_path, monkeypatch):
    """Test adding items and listing them."""
    monkeypatch.setattr("skill._DATA_FILE", tmp_path / "groceries.json")

    result = add_grocery_item.invoke({"item": "milk"})
    assert "Added 'milk'" in result

    result = list_groceries.invoke({})
    assert "milk" in result


def test_clear(tmp_path, monkeypatch):
    """Test clearing the list."""
    monkeypatch.setattr("skill._DATA_FILE", tmp_path / "groceries.json")

    add_grocery_item.invoke({"item": "eggs"})
    clear_groceries.invoke({})

    result = list_groceries.invoke({})
    assert "empty" in result
```

---

## Async Skills

If your skill needs to make async calls (HTTP requests, database queries), use `async def`:

```python title="workspace/skills/my-skill/skill.py"
import httpx
from langchain_core.tools import tool


@tool
async def fetch_recipe(query: str) -> str:
    """Search for a recipe online.

    Args:
        query: What to search for (e.g. "pasta carbonara").
    """
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.example.com/recipes",
            params={"q": query},
        )
    resp.raise_for_status()
    data = resp.json()
    if not data["results"]:
        return "No recipes found."
    recipe = data["results"][0]
    return f"**{recipe['title']}**\n{recipe['url']}"
```

---

## Summary

| Step | What You Did |
|------|-------------|
| 1 | Created `workspace/skills/my-skill/` directory |
| 2 | Wrote `SKILL.md` with YAML frontmatter description |
| 3 | Implemented `@tool` functions in `skill.py` |
| 4 | (Optional) Added `requires_env` or `requires_bridge` gating |
| 5 | Verified discovery in logs after restart |
| 6 | Tested via Telegram and unit tests |
