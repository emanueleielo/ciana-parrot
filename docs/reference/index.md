# API Reference

Complete API documentation for every public module in CianaParrot. Each page documents classes, methods, parameters, return types, and includes code snippets taken directly from the source.

## Modules

| Module | Description | Source |
|--------|-------------|--------|
| [Channels](api/channels.md) | Abstract channel interface, Telegram adapter, message dataclasses, and mode handler protocol | `src/channels/` |
| [Bridges](api/bridges.md) | Claude Code bridge -- project/conversation browsing and CLI execution | `src/gateway/bridges/claude_code/` |
| [Gateway](api/gateway.md) | Host gateway server and async HTTP client for secure command execution | `src/gateway/` |
| [Tools](api/tools.md) | Agent-callable tools: web search/fetch, scheduled tasks, and host execution | `src/tools/` |
| [Config](api/config.md) | Pydantic v2 configuration models and YAML loader with env-var expansion | `src/config.py` |
| [Router](api/router.md) | Message routing: trigger detection, user allowlist, thread mapping, session logging | `src/router.py` |
| [Scheduler](api/scheduler.md) | Async task scheduler supporting cron, interval, and one-shot execution | `src/scheduler.py` |
| [Agent](api/agent.md) | Agent factory and workspace shell backend with sandboxed execution | `src/agent.py`, `src/backend.py` |
| [Middleware](api/middleware.md) | Skill filtering by environment variables and bridge availability | `src/middleware.py` |

## Architecture at a Glance

```
Telegram polling
  -> TelegramChannel._handle_message()
    -> IncomingMessage (normalized dataclass)
    -> MessageRouter.handle_message()
      -> user allowlist check
      -> trigger detection
      -> thread_id mapping
      -> agent.ainvoke() with LangGraph persistence
      -> JSONL session log
    -> response sent via TelegramChannel.send()
```

## Conventions

- **Async-first**: all I/O operations use `async def`
- **Module-level config**: tools use `init_*()` to set globals at startup, then `@tool`-decorated functions read those globals
- **Pydantic v2**: all configuration validated via `BaseModel` subclasses
- **Type hints**: used throughout the codebase
