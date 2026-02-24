---
title: Installation
---

# Installation

This page covers prerequisites, cloning the repository, configuring secrets, and building the Docker image.

---

## Prerequisites

Before installing CianaParrot, make sure you have the following:

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Python** | 3.13+ | Required for local development and testing. Not needed if you only run via Docker. |
| **Docker** | 20.10+ | Container runtime for the bot. |
| **Docker Compose** | v2+ | Orchestrates the container and volumes. Bundled with Docker Desktop. |
| **Telegram Bot Token** | -- | Obtained from [@BotFather](https://t.me/BotFather) on Telegram. |

!!! info "Getting a Telegram bot token"
    1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
    2. Send `/newbot` and follow the prompts to choose a name and username.
    3. BotFather will reply with a token like `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`.
    4. Copy this token -- you will need it in the next step.

---

## One-Command Install

The fastest way to get started:

```bash
curl -fsSL https://raw.githubusercontent.com/emanueleielo/ciana-parrot/main/install.sh | bash
```

The installer handles everything: prerequisites check, repo clone, `.env` setup (prompts for your API keys interactively), Docker build, and host gateway startup.

**Flags:**

| Flag | Description |
|------|-------------|
| `--dry-run` | Preview all actions without making any changes. |
| `--no-prompt` | Non-interactive mode -- reads API keys from environment variables. Suitable for CI. |
| `--help` | Show usage information. |

If you prefer to set things up manually, continue below.

---

## Manual Installation

### 1. Clone the Repository

```bash
git clone https://github.com/emanueleielo/ciana-parrot.git
cd ciana-parrot
```

### 2. Configure Secrets

Copy the example environment file and fill in your API keys:

```bash
cp .env.example .env
```

Open `.env` in your editor and set at minimum:

```dotenv
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
```

!!! warning "Never commit `.env`"
    The `.env` file contains secrets and is listed in `.gitignore`. Never commit it to version control.

Optional keys (enable additional features):

| Variable | Purpose |
|----------|---------|
| `BRAVE_API_KEY` | Brave Search API (falls back to DuckDuckGo if not set) |
| `OPENAI_API_KEY` | Voice transcription via Whisper |
| `GATEWAY_TOKEN` | Authentication for the host gateway |
| `CC_BRIDGE_TOKEN` | Authentication for the Claude Code bridge |
| `LANGSMITH_API_KEY` | LangSmith tracing for observability |

### 3. Build and Run

```bash
make build    # Build the Docker image
make up       # Start the container in the background
```

Verify the bot is running:

```bash
make logs     # Follow container logs (Ctrl+C to exit)
```

You should see the bot start up, load its configuration, and begin polling Telegram for messages.

### 4. Start the Host Gateway (Optional)

If you want the agent to interact with host applications (Spotify, Apple Reminders, Claude Code, etc.), start the gateway on your host machine:

```bash
make gateway
```

The gateway runs on port 9842 and validates all commands against per-bridge allowlists. See [Configuration](configuration.md) for details on enabling bridges.

---

## Post-Clone Setup

After a fresh clone, run this command to prevent your personal memory file from being tracked by git:

```bash
git update-index --skip-worktree workspace/MEMORY.md
```

!!! note "Why skip-worktree?"
    `workspace/MEMORY.md` is the agent's persistent memory -- it contains personal data that the agent accumulates over time. The template is committed to the repository, but your local changes should never be pushed. The `skip-worktree` flag tells git to ignore local modifications to this file.

---

## Makefile Reference

All common operations are available through `make`:

| Command | Description |
|---------|-------------|
| `make build` | Build the Docker image |
| `make up` | Start the container in the background |
| `make down` | Stop the container |
| `make logs` | Follow container logs |
| `make restart` | Rebuild and restart |
| `make shell` | Open a shell inside the container |
| `make test` | Run the test suite (pytest) |
| `make gateway` | Start the host gateway on port 9842 |

---

## Next Steps

Once the bot is running, head to [First Run](first-run.md) to send your first message and explore the bot commands.
