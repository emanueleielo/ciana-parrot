---
title: Getting Started
---

# Getting Started

This section walks you through setting up CianaParrot from scratch: installing prerequisites, running the bot for the first time, and understanding the configuration file.

---

## In This Section

<div class="grid cards" markdown>

-   **[Installation](installation.md)**

    ---

    Prerequisites, cloning the repo, setting up secrets, and building the Docker image.

-   **[First Run](first-run.md)**

    ---

    Sending your first message, understanding group vs. DM behavior, and verifying the bot is running.

-   **[Configuration](configuration.md)**

    ---

    Complete walkthrough of `config.yaml` -- every section explained, with tips for common setups.

</div>

---

## The Short Version

If you want to get up and running as fast as possible:

```bash
# One-command install (handles everything)
curl -fsSL https://raw.githubusercontent.com/emanueleielo/ciana-parrot/main/install.sh | bash
```

Or manually:

```bash
git clone https://github.com/emanueleielo/ciana-parrot.git
cd ciana-parrot
cp .env.example .env       # Fill in your API keys
make build && make up       # Build and start
make gateway                # Start the host gateway (optional)
```

Then open your bot on Telegram and send `/start`.

!!! tip "What next?"
    After your first run, head to [Configuration](configuration.md) to fine-tune the LLM provider, enable bridges, set up scheduled tasks, and connect MCP servers.
