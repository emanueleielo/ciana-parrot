---
title: First Run
---

# First Run

Your bot is built and running. This page covers sending your first message, understanding how the bot behaves in different chat contexts, and verifying everything is working.

---

## Send Your First Message

1. Open Telegram and search for your bot by its username (the one you chose with BotFather).
2. Press **Start** or send `/start`.
3. The bot will reply with a welcome message.
4. Send any message -- the agent will respond using the configured LLM provider.

That's it. The bot is live and ready to chat.

---

## Group Chats vs. Direct Messages

CianaParrot behaves differently depending on the chat context:

| Context | Behavior |
|---------|----------|
| **Direct message (DM)** | The bot responds to every message. No prefix needed. |
| **Group chat** | The bot only responds when the message starts with the configured trigger (default: `@Ciana`). |

The trigger is configurable in `config.yaml`:

```yaml
channels:
  telegram:
    trigger: "@Ciana"    # Change this to your preferred prefix
```

!!! tip "Group chat example"
    In a group, send `@Ciana what's the weather today?` and the bot will respond. Messages without the trigger are silently ignored.

---

## Bot Commands

CianaParrot registers several Telegram commands:

| Command | Description |
|---------|-------------|
| `/start` | Displays a welcome message and confirms the bot is active. |
| `/help` | Lists all available commands. |
| `/new` | Resets the current conversation session. The bot starts fresh with no memory of previous messages in this thread. The persistent memory file (`MEMORY.md`) is not affected. |
| `/status` | Shows system status: uptime, loaded tools, active bridges, and scheduler state. |
| `/cc` | Enters Claude Code mode. See [Claude Code Mode](#claude-code-mode) below. |
| `/cc exit` | Exits Claude Code mode and returns to normal chat. |

!!! info "Session persistence"
    Conversation history is stored in an SQLite database (`workspace/checkpoints.db`) and survives container restarts. Use `/new` to start a fresh session when you want a clean slate.

---

## Claude Code Mode

The `/cc` command activates Claude Code mode, which lets you interact with [Claude Code](https://claude.ai/code) directly from Telegram.

When you enter `/cc`:

1. An inline keyboard appears with your available projects (paginated if you have many).
2. Select a project, then choose an existing conversation to resume or start a new one.
3. All subsequent messages are forwarded to Claude Code instead of the main CianaParrot agent.
4. Responses stream back with tool-call details that can be expanded/collapsed.

Use `/cc exit` to leave Claude Code mode and return to the normal assistant.

!!! note "Prerequisites"
    Claude Code mode requires the host gateway to be running and the `claude-code` bridge to be configured. See [Configuration](configuration.md) for setup details.

---

## Verifying the Bot

If the bot is not responding, check the container logs:

```bash
make logs
```

You should see output similar to:

```
INFO  - Loading config from config.yaml
INFO  - Initializing agent with provider anthropic/claude-sonnet-4-6
INFO  - Loaded 12 tools
INFO  - Telegram channel started, polling for messages...
```

Common issues:

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Container exits immediately | Missing or invalid API key | Check `.env` for `ANTHROPIC_API_KEY` and `TELEGRAM_BOT_TOKEN` |
| Bot online but not responding | Wrong trigger in group chat | Send a DM first to confirm the bot works, then check the `trigger` setting |
| "Unauthorized" in logs | Invalid Telegram token | Verify the token with [@BotFather](https://t.me/BotFather) |
| Gateway errors | Gateway not running | Run `make gateway` on the host |

!!! tip "Debug logging"
    For more detailed output, set the logging level to `DEBUG` in `config.yaml`:

    ```yaml
    logging:
      level: "DEBUG"
    ```

    Then restart with `make restart`.

---

## Next Steps

Now that your bot is running and responding, head to [Configuration](configuration.md) for a complete walkthrough of every setting in `config.yaml`.
