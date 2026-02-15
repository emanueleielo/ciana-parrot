# Contributing to CianaParrot

Thanks for your interest in contributing!

## Getting Started

1. Fork the repository
2. Clone your fork
3. Copy `.env.example` to `.env` and add your API keys
4. Build and run with Docker:

```bash
make build
make up
make logs
```

## Making Changes

- Create a feature branch from `main`
- Keep changes focused — one feature or fix per PR
- Test your changes locally before submitting

## Adding a New Channel

1. Create `src/channels/yourservice.py`
2. Implement `AbstractChannel` (see `src/channels/base.py`)
3. Add config section in `config.yaml`
4. Wire it in `src/main.py`

## Adding a Skill

1. Create `skills/your-skill/SKILL.md` with description
2. Create `skills/your-skill/skill.py` with tool functions
3. Functions with docstrings are auto-registered as agent tools

## Code Style

- Python 3.13+
- Use type hints
- Keep functions short and focused
- No unnecessary abstractions

## Pull Requests

- Write a clear description of what changed and why
- Reference any related issues
- Make sure the bot starts and responds correctly

## Reporting Issues

Open an issue with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Logs if relevant (`make logs`)
