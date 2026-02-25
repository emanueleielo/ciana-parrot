# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] — 2026-02-25

### Added

- Multi-tier model router with dynamic tier switching (`RoutingChatModel`, `switch_model` tool, per-task tier in scheduler)
- One-command installer (`install.sh`) with dry-run support and gateway dependency setup
- 14 new skills for host gateway bridges (1Password, Apple Reminders, Bear Notes, BluCLI, CamSnap, iMessage, Obsidian, OpenHue, Peekaboo, Sonos, Spotify, Things, Troubleshooting, WhatsApp)
- WhatsApp `wacli-daemon` for background sync management
- Comprehensive documentation site (user guides, architecture, contributing, configuration reference)
- Skill creation guide

### Changed

- Host bridge system refactored into gateway architecture with client/server split and `host_execute` tool
- Enhanced error handling, input validation, and security measures across multiple modules
- Improved tool display names, bridge icons, and session counter sync

### Fixed

- Gateway `timeout=0` now treated as no limit instead of default timeout
- Installer dry-run prerequisite check and gateway dependency fallback
- Installer crash on awk corruption and path consistency issues

### Security

- Pre-commit hook for gitleaks secret scanning

## [0.3.1] — 2026-02-23

### Changed

- Extracted `ToolDetailsManager` from duplicated tool-details expand/collapse logic in `TelegramChannel` and `ClaudeCodeHandler` into shared `src/channels/telegram/tool_details.py`
- 13 tests for `ToolDetailsManager` (store, buttons, expand/collapse, prefix isolation, eviction, BadRequest fallback)

## [0.3.0] — 2026-02-22

### Added

- Skill auto-creation with sandboxed execution and workspace isolation
- Skill catalog with environment-based auto-filtering for available skills
- Voice message transcription and photo support via Telegram
- Markdown table rendering as aligned monospace blocks in Telegram
- `/cc` slash commands in Telegram Claude Code mode with improved timeout handling

### Changed

- Dockerfile hardening for skill execution environment
- Updated `.gitignore` with runtime data entries
- Added parrot SVG logo and cianaparrot.dev website badge to README
- Rebranded host bridge system as secure host gateway architecture in README

## [0.2.0] — 2026-02-19

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
- Extracted magic numbers to named constants
- Narrowed broad exception handlers to specific exception types
- Removed unused imports and variables
- Updated architecture diagram (PNG → SVG)
- Updated README with bridge system, observability, and accurate project structure

## [0.1.0] — 2026-02-15

### Added

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

[0.4.0]: https://github.com/emanueleielo/ciana-parrot/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/emanueleielo/ciana-parrot/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/emanueleielo/ciana-parrot/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/emanueleielo/ciana-parrot/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/emanueleielo/ciana-parrot/releases/tag/v0.1.0
