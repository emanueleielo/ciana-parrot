---
title: Development Setup
---

# Development Setup

This page walks you through setting up a local development environment for CianaParrot, from cloning the repository to running the bot and previewing documentation.

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Python** | 3.13+ | Required for running locally and executing tests |
| **Docker** | 20.10+ | Container runtime for production-style runs |
| **Docker Compose** | v2+ | Orchestrates the container and volumes |
| **Git** | 2.30+ | Version control |

---

## Step-by-Step Setup

### 1. Clone the Repository

```bash
git clone https://github.com/emanueleielo/ciana-parrot && cd ciana-parrot
```

### 2. Create a Virtual Environment

Python 3.13 or later is required.

```bash
python3 -m venv .venv && source .venv/bin/activate
```

!!! tip "Verify your Python version"
    ```bash
    python3 --version
    ```
    If your default `python3` is older than 3.13, install the correct version via [pyenv](https://github.com/pyenv/pyenv) or your system package manager.

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

Open `.env` in your editor and fill in at minimum:

```dotenv
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
ANTHROPIC_API_KEY=sk-ant-...       # or your preferred provider's key
```

!!! warning "Never commit `.env`"
    The `.env` file contains secrets and is listed in `.gitignore`. Never add it to version control.

### 5. Post-Clone Git Setup

After a fresh clone, prevent your personal memory file from being tracked:

```bash
git update-index --skip-worktree workspace/MEMORY.md
```

!!! info "Why this matters"
    `workspace/MEMORY.md` contains personal data the agent accumulates over time. The template is committed to the repo, but your local changes must never be pushed. See [Git Guidelines](git-guidelines.md) for details.

### 6. Run Locally

```bash
python -m src.main
```

The bot will start polling Telegram for messages. Send `/start` to your bot to verify it is working.

### 7. Run with Docker

For a production-style environment:

```bash
make build && make up
```

Verify the bot is running:

```bash
make logs
```

### 8. Start the Host Gateway (Optional)

If you need host application integrations (Spotify, Apple Reminders, Claude Code, etc.), start the gateway in a separate terminal:

```bash
make gateway
```

The gateway runs on port 9842 and validates all commands against per-bridge allowlists.

### 9. Preview Documentation

To preview the MkDocs documentation site locally:

```bash
make docs
```

This starts a local server at [http://localhost:8000](http://localhost:8000) with live reload.

---

## Makefile Reference

All common operations are available through `make`:

| Command | Description |
|---------|-------------|
| `make build` | Build the Docker image via `docker compose build` |
| `make up` | Start the container in the background via `docker compose up -d` |
| `make down` | Stop the container via `docker compose down` |
| `make logs` | Follow container logs via `docker compose logs -f cianaparrot` |
| `make restart` | Rebuild and restart the container |
| `make shell` | Open a shell inside the running container |
| `make test` | Run the test suite with `python3 -m pytest tests/ -v` |
| `make gateway` | Start the host gateway on port 9842 |
| `make docs` | Start a local MkDocs preview server at localhost:8000 |
| `make docs-build` | Build the static documentation site |

---

## Project Layout

A quick orientation of the key directories:

```
ciana-parrot/
  src/                  # Main application source
    channels/           # Channel adapters (Telegram, etc.)
    gateway/            # Gateway server, client, bridges
    tools/              # Agent tools (web, cron, host)
    config.py           # Pydantic config models
    main.py             # Entry point
    agent.py            # Agent construction
    router.py           # Message routing
    scheduler.py        # Scheduled task execution
  tests/                # Pytest test suite
  skills/               # Skill plugins (SKILL.md + skill.py)
  workspace/            # Agent workspace (memory, checkpoints, sessions)
  data/                 # Runtime data (scheduled tasks, allowed users)
  docs/                 # MkDocs documentation source
  config.yaml           # Application configuration
  docker-compose.yml    # Container orchestration
  Makefile              # Build and run shortcuts
```

---

## Next Steps

- Run the test suite: [Testing](testing.md)
- Understand code standards: [Code Conventions](code-conventions.md)
- Learn the git workflow: [Git Guidelines](git-guidelines.md)
