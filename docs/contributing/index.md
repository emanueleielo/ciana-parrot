---
title: Contributing
---

# Contributing

Thank you for your interest in contributing to CianaParrot. Whether you are reporting a bug, proposing a feature, improving documentation, or building a new skill -- every contribution is welcome.

---

## Ways to Contribute

<div class="grid cards" markdown>

-   **Bug Reports**

    ---

    Found something broken? Open an issue on GitHub with steps to reproduce, expected vs. actual behavior, and relevant logs.

-   **Feature Requests**

    ---

    Have an idea for a new capability? Open an issue describing the use case and how you envision it working. Discussion before implementation saves everyone time.

-   **Code Contributions**

    ---

    Bug fixes, new features, performance improvements, refactoring. See [Development Setup](development-setup.md) to get your local environment ready.

-   **New Skills**

    ---

    Skills are self-contained plugins that add tools to the agent. Drop a folder in `skills/` with a `SKILL.md` and `skill.py` -- functions with docstrings auto-register as agent tools.

-   **New Bridges**

    ---

    Bridges connect the sandboxed agent to host applications. If you have an app integration in mind, a bridge contribution lets every CianaParrot user benefit.

-   **Documentation**

    ---

    Improvements to these docs, new guides, better examples, typo fixes. Run `make docs` locally to preview your changes.

</div>

---

## Before You Start

!!! tip "Check existing issues first"
    Before starting work on a feature or fix, search the [GitHub issues](https://github.com/emanueleielo/ciana-parrot/issues) to see if someone is already working on it. If not, open one to discuss your approach.

---

## In This Section

| Page | Description |
|------|-------------|
| [Development Setup](development-setup.md) | Local environment, dependencies, Docker, and Makefile reference |
| [Testing](testing.md) | Running tests, writing new tests, and test conventions |
| [Code Conventions](code-conventions.md) | Type hints, async patterns, naming, and project structure |
| [Git Guidelines](git-guidelines.md) | Commit messages, protected files, pre-commit hooks, and branching |

---

## Quick Reference

```bash
# Clone and set up
git clone https://github.com/emanueleielo/ciana-parrot && cd ciana-parrot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in your keys
git update-index --skip-worktree workspace/MEMORY.md

# Run locally
python -m src.main

# Run tests
make test

# Preview docs
make docs
```
