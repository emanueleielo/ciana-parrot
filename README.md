<p align="center">
  <a href="https://cianaparrot.dev">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="images/parrot-logo.svg">
      <source media="(prefers-color-scheme: light)" srcset="images/parrot-logo-light.svg">
      <img src="images/parrot-logo.svg" alt="CianaParrot" width="460">
    </picture>
  </a>
</p>

<p align="center">
  <strong>Self-hosted AI assistant with multi-channel support, scheduled tasks, and extensible skills.</strong>
</p>

<p align="center">
  <a href="https://docs.cianaparrot.dev"><img src="https://img.shields.io/badge/docs-docs.cianaparrot.dev-00F0FF?style=flat&logo=readthedocs&logoColor=white" alt="Docs"></a>
  <a href="https://cianaparrot.dev"><img src="https://img.shields.io/badge/website-cianaparrot.dev-00F0FF?style=flat&logo=vercel&logoColor=white" alt="Website"></a>
  <img src="https://img.shields.io/badge/python-3.13+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/framework-DeepAgents-orange" alt="DeepAgents">
  <img src="https://img.shields.io/badge/deploy-Docker-2496ED?logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
</p>

---

CianaParrot is a self-hosted AI personal assistant that runs on your own infrastructure — sandboxed inside Docker, but connected to your OS through secure bridges. Built on the [DeepAgents](https://github.com/deepagents/deepagents) framework with LangChain/LangGraph, it combines interactive chat via Telegram with autonomous scheduled tasks — all configured through a single YAML file.

## Features

- **Multi-provider LLM** — Anthropic, OpenAI, Google Gemini, Groq, Ollama, OpenRouter, vLLM
- **Multi-channel** — Pluggable channel architecture, Telegram out of the box
- **Host gateway** — Secure bridge system connecting the Docker sandbox to host CLI tools (Spotify, Reminders, iMessage, Things, Bear Notes, Obsidian, 1Password, HomeKit, and more)
- **Scheduled tasks** — Cron, interval, and one-shot tasks the agent can create via chat
- **Skills system** — Drop a folder in `skills/` and it auto-registers as agent tools
- **MCP support** — Connect external MCP servers for unlimited extensibility
- **Persistent memory** — Markdown-based identity and memory the agent updates itself
- **Observability** — Optional LangSmith tracing
- **Docker-only deploy** — One command to build, one to run

## Architecture

<p align="center">
  <img src="images/architecture.svg" alt="CianaParrot Architecture" width="800">
</p>

## Quick Start

### One-command install

```bash
curl -fsSL https://raw.githubusercontent.com/emanueleielo/ciana-parrot/main/install.sh | bash
```

This handles everything: prerequisites check, repo clone, `.env` setup (prompts for API keys), Docker build, and host gateway startup.

> **Flags:** `bash install.sh --dry-run` to preview without changes, `--no-prompt` for non-interactive/CI usage.

### Manual setup

```bash
git clone https://github.com/emanueleielo/ciana-parrot.git
cd ciana-parrot
cp .env.example .env     # Edit with your API keys
make build && make up    # Build and start
make gateway             # Start host gateway (optional)
```

Open your bot on Telegram, send `/start`, and start chatting.

## Documentation

Full documentation is available at **[docs.cianaparrot.dev](https://docs.cianaparrot.dev)**, including:

- [Getting Started](https://docs.cianaparrot.dev/getting-started/) — Installation, setup, and first run
- [Architecture](https://docs.cianaparrot.dev/architecture/) — Message flow, gateway system, persistence
- [Guides](https://docs.cianaparrot.dev/guides/) — Channels, bridges, skills, configuration, agent customization
- [Reference](https://docs.cianaparrot.dev/reference/) — API docs, config reference, Telegram commands
- [Contributing](https://docs.cianaparrot.dev/contributing/) — Dev environment, testing, code style

## License

MIT
