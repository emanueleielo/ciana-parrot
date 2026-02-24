---
title: Home
---

# CianaParrot

**Your AI copilot, from your own station.**

CianaParrot is a self-hosted AI personal assistant that combines interactive chat via Telegram with autonomous scheduled tasks -- all running on your own infrastructure. Built on the [DeepAgents](https://github.com/deepagents/deepagents) framework with LangChain/LangGraph, it gives you a capable AI agent sandboxed inside Docker but securely connected to your OS through a bridge system.

---

## Feature Highlights

<div class="grid cards" markdown>

-   **Multi-Channel Chat**

    ---

    Telegram out of the box with a pluggable adapter pattern for adding new channels. Group chat trigger support and per-user access control.

-   **Scheduled Tasks**

    ---

    Cron expressions, fixed intervals, and one-shot timers. The agent creates and manages tasks through natural language -- persisted across restarts.

-   **Host Gateway & Bridges**

    ---

    A secure bridge system connects the sandboxed agent to macOS apps: Apple Reminders, Spotify, Things 3, iMessage, WhatsApp, Bear Notes, Obsidian, Sonos, Philips Hue, 1Password, and more.

-   **Skills System**

    ---

    Drop a folder in `skills/` with a `SKILL.md` and a `skill.py` -- functions with docstrings auto-register as agent tools via DeepAgents.

-   **Claude Code via Telegram**

    ---

    Full Claude Code sessions from Telegram. Select a project, pick or start a conversation, and send messages directly to Claude Code with streaming output and tool-call rendering.

-   **Web Search & Fetch**

    ---

    Built-in web search (Brave Search or DuckDuckGo fallback) and URL fetching. The agent can research topics, pull live data, and summarize web pages.

-   **MCP Server Support**

    ---

    Connect external [Model Context Protocol](https://modelcontextprotocol.io) servers for unlimited extensibility -- filesystem access, databases, custom APIs.

-   **Voice Message Transcription**

    ---

    Voice messages sent to the bot are automatically transcribed using OpenAI Whisper or Groq, then processed as regular text input.

</div>

---

## Quick Start

Get CianaParrot running with a single command:

```bash
curl -fsSL https://raw.githubusercontent.com/emanueleielo/ciana-parrot/main/install.sh | bash
```

This handles prerequisites, repo clone, `.env` setup (prompts for API keys), Docker build, and host gateway startup.

Or follow the step-by-step [Installation Guide](getting-started/installation.md).

---

## Documentation

| Section | Description |
|---------|-------------|
| [Getting Started](getting-started/index.md) | Installation, first run, and configuration walkthrough |
| [Architecture](architecture/index.md) | Message flow, gateway system, and persistence internals |
| [Guides](guides/index.md) | How to add channels, bridges, skills, tools, and mode handlers |
| [Reference](reference/index.md) | API docs, config reference, skill format, and Telegram commands |
| [Contributing](contributing/index.md) | Development setup, testing, code conventions, and git guidelines |

---

## At a Glance

| | |
|---|---|
| **Language** | Python 3.13+ |
| **Framework** | DeepAgents + LangChain/LangGraph |
| **Deployment** | Docker / Docker Compose |
| **License** | MIT |
| **Author** | Emanuele Ielo |
| **Repository** | [github.com/emanueleielo/ciana-parrot](https://github.com/emanueleielo/ciana-parrot) |
