---
name: skill-creation
description: "Guide for creating, updating, and managing skills. Use when: you need to extend your capabilities with a new skill, or the user asks you to create one. Skills are persistent Markdown instruction modules auto-discovered at runtime."
---

# Skill Creation

You can create new skills to extend your own capabilities. Skills are Markdown instruction modules that persist across conversations and require no restart.

## When to Create a Skill

- A recurring task that benefits from a structured workflow
- Domain knowledge worth preserving across conversations
- A multi-step process the user asks about repeatedly
- Integration with a new CLI tool or API

## When NOT to Create a Skill

- One-off tasks that won't recur
- Information that belongs in MEMORY.md (user preferences, personal facts)
- Temporary instructions or experiment notes

## How to Create a Skill

1. Choose a name: lowercase, digits, hyphens only (e.g., `meeting-notes`, `code-review`)
2. Create the file using **write_file**:

```
write_file("skills/<name>/SKILL.md", content)
```

3. The skill is available immediately on the next message — no restart needed
4. Always tell the user when you create a new skill

## SKILL.md Format

Every skill needs a YAML frontmatter block followed by Markdown instructions:

```markdown
---
name: <skill-name>
description: "Brief description of what this skill does and when to use it. Max 1024 chars."
---

# Skill Title

Instructions in markdown...
```

### Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Must match the directory name exactly |
| `description` | Yes | What the skill does and when to use it. Max 1024 chars |
| `requires_env` | No | List of environment variables needed (skill is hidden if missing) |
| `requires_bridge` | No | Host gateway bridge name required (skill is hidden if bridge unavailable) |
| `homepage` | No | External URL for reference documentation |
| `metadata` | No | Provider-specific metadata (e.g., OpenClaw) |

### Frontmatter Examples

**Simple skill (no dependencies):**

```yaml
---
name: meeting-notes
description: "Generate structured meeting notes from conversations. Use when the user asks to summarize or document a meeting."
---
```

**Skill requiring an API key:**

```yaml
---
name: notion
description: "Manage Notion workspace: create pages, query databases, add content blocks. Requires NOTION_API_KEY."
requires_env:
  - NOTION_API_KEY
---
```

**Skill requiring a host bridge:**

```yaml
---
name: spotify
description: "Control Spotify playback: play, pause, skip, search tracks/albums/playlists via spogo CLI."
requires_bridge: "spotify"
---
```

## Body Structure

Follow this structure for the Markdown body:

```markdown
# Skill Title

Brief one-line summary.

## When to Use

- Trigger phrase or scenario 1
- Trigger phrase or scenario 2

## When NOT to Use

- Scenario where another approach is better

## Commands / Workflow

Step-by-step instructions, code blocks, curl examples, etc.

## Notes

- Caveats, rate limits, known issues
```

### Guidelines for the Body

- **Be procedural**: write steps the agent can follow, not conceptual explanations
- **Include concrete examples**: real commands, API calls, curl snippets
- **Use code blocks** with language hints for syntax highlighting
- **Document known issues** and workarounds — these save the most time
- **Keep it concise**: aim for what's needed to execute, not exhaustive documentation

## Rules

- Only create `SKILL.md` files — never create Python scripts or executable code in skill directories
- The `name` in frontmatter MUST match the directory name
- One skill per directory, one `SKILL.md` per skill
- You can add supporting files (configs, docs) in the same directory if needed
- You can update or delete your own skills when they become outdated
- Always verify the skill works by reading it back after creation

## Updating & Deleting Skills

- **Update**: use `edit_file` or `write_file` to modify `skills/<name>/SKILL.md`
- **Delete**: remove the skill directory (tell the user first)
- Changes take effect on the next message — no restart needed
