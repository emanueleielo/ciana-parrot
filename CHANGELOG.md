# Changelog

## 0.2.0 — 2026-02-19

### Added

- Claude Code bridge for Telegram — forward messages to a Claude Code CLI session via `/cc` command
- Conversation and project selection with inline keyboards and pagination
- Unified tool display between normal agent and Claude Code modes
- SQLite-based conversation persistence replacing in-memory checkpointer (`AsyncSqliteSaver`)
- Filesystem sandboxing with `virtual_mode=True` (agent confined to `workspace/`)
- Markdown-to-HTML conversion for Telegram output with code block protection and 4096-char chunking
- Host filesystem access via Docker volume mounts

### Fixed

- `/new` command now properly resets the session
- Reply keyboard no longer disappears in Claude Code mode
- Code review findings applied across 10 files

### Changed

- Default LLM provider updated to `claude-sonnet-4-6` with temperature 0
- Config comments translated to English
- Protected runtime data and credentials from repository

### Improved

- Extracted magic numbers to named constants
- Narrowed broad exception handlers to specific exception types
- Removed unused imports and variables
- Updated architecture diagram (PNG → SVG)
- Updated README with bridge system, observability, and accurate project structure

## 0.1.0 — 2026-02-15

Initial release.

- DeepAgents-based agent with memory, filesystem sandbox, and session persistence
- Telegram channel with trigger detection, commands, typing indicator
- Multi-provider LLM support (Anthropic, OpenAI, Google Gemini, Groq, Ollama, OpenRouter, vLLM)
- Web search (Brave / DuckDuckGo) and URL fetch tools
- Scheduled tasks (cron, interval, one-shot)
- MCP server integration
- Skills system with auto-discovery
- User allowlist per channel
- Markdown-based identity, agent instructions, and persistent memory
- Docker-only deployment with Makefile
