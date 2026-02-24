---
title: Telegram Commands
---

# Telegram Commands Reference

Complete reference for all bot commands, Claude Code mode commands, and interactive UI elements.

## Bot Commands

These commands are always available:

| Command | Description | Context |
|---------|-------------|---------|
| `/start` | Welcome message | Any chat |
| `/help` | Show available commands | Any chat |
| `/new` | Reset session — starts a new conversation | Any chat |
| `/status` | System status check | Any chat |
| `/cc` | Enter Claude Code mode (project selection) | Private chat only |
| `/cc exit` | Exit Claude Code mode | Private chat only |

## Chat Behavior

### Private Chats (DMs)

The bot responds to every message. No trigger prefix needed.

### Group Chats

Messages must start with the configured trigger (default: `@Ciana`):

```
@Ciana what's the weather like?
```

The trigger is stripped before sending to the agent. Configure it in `config.yaml`:

```yaml
channels:
  telegram:
    trigger: "@Ciana"
```

### User Allowlist

If `allowed_users` is set, only listed user IDs can interact:

```yaml
channels:
  telegram:
    allowed_users: ["123456789", "987654321"]
```

Empty list = allow all users.

## Session Management

### /new — Session Reset

Resets the conversation by incrementing a session counter. The thread ID changes from `telegram_12345` to `telegram_12345_s1`, `_s2`, etc.

- Previous conversations are preserved in the checkpoint database
- The agent starts fresh with no prior context
- Session counters survive container restarts (persisted in `data/session_counters.json`)

## Claude Code Mode

### Entering CC Mode

1. Send `/cc` in a private chat
2. Select a project from the inline keyboard (paginated)
3. Select an existing conversation or start a new one
4. All messages now go to Claude Code instead of Ciana

### CC Mode Commands

While in Claude Code mode, prefix commands with `cc:`:

| Command | Description |
|---------|-------------|
| `cc:help` | Show CC-specific commands |
| `cc:model [name]` | Show or switch model (e.g., `cc:model sonnet`) |
| `cc:effort [level]` | Set effort level: `low`, `medium`, or `high` |
| `cc:compact` | Fork session to reduce context (creates new session from current) |
| `cc:clear` | Start new conversation in the same project |
| `cc:status` | Show current project, session, model, and effort |
| `cc:cost` | Token usage info (not available in piped mode) |

### Reply Keyboard Buttons

When in CC mode, a persistent reply keyboard appears:

| Button | Action |
|--------|--------|
| Conversations | Show conversation list for the active project |
| Exit CC | Exit Claude Code mode, return to Ciana |

### Inline Keyboards

**Project list** (from `/cc`):

- Each project shows: display name, conversation count, last activity
- Paginated (6 items per page)

**Conversation list** (after selecting project):

- Each conversation shows: first message preview, relative time, git branch
- Paginated (6 items per page)
- "+ New session" button to start fresh
- "Projects" button to go back

**Active session** (after selecting conversation):

- "Switch Project" — return to project list
- "Exit CC" — exit Claude Code mode

### CC Mode Behavior

- **Text messages** → forwarded to Claude Code CLI
- **Voice messages** → transcribed first, then forwarded as text
- **Photos** → not supported in CC mode (error message shown)
- **Responses** → rendered with tool details (expandable inline button)
- **Processing** → shows "Processing..." placeholder that gets edited with the response
- **Timeout** — 300-second timeout per message; shows friendly message if exceeded
- **Concurrency** — per-user lock prevents message interleaving

## Tool Details

When the agent (or Claude Code) uses tools, responses include an expandable "Tool details" inline button. Clicking it shows which tools were called, their inputs, and results.

## Voice Messages

If transcription is configured, voice messages are automatically transcribed and processed as text:

```yaml
transcription:
  enabled: true
  provider: "openai"
  model: "whisper-1"
  api_key: "${OPENAI_API_KEY}"
```

If transcription is not configured, voice messages are rejected with a friendly message.

## Photo Messages

Photos are supported in normal mode (not CC mode):

- The highest-resolution version is downloaded
- Encoded as base64 and sent to the agent as a multimodal message
- Caption text (if any) is included
