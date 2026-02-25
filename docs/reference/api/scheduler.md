---
title: Scheduler API
---

# Scheduler API

::: src.scheduler

**Module:** `src/scheduler.py`

The scheduler runs as an asyncio background task, polling `data/scheduled_tasks.json` for due tasks.

## Scheduler

```python
class Scheduler:
    def __init__(self, agent, config: AppConfig, channels: dict = None): ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
```

### `__init__(agent, config, channels=None)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `agent` | LangGraph agent | The agent instance to invoke for task execution |
| `config` | `AppConfig` | Application config (reads `scheduler.poll_interval`, `scheduler.data_file`) |
| `channels` | `dict[str, AbstractChannel]` | Map of channel name to channel instance for sending results |

### `start()`

Creates an `asyncio.Task` running the polling loop. The loop calls `_check_and_run()` every `poll_interval` seconds.

### `stop()`

Cancels the polling task and drains any in-flight task executions via `asyncio.gather()`.

## Polling Loop

The scheduler checks for due tasks under a shared `asyncio.Lock` (same lock used by cron tools) to prevent race conditions:

```python
async with get_tasks_lock():
    # Read tasks, mark due ones, write back
    ...

# Execute due tasks in parallel, outside the lock
for task in due_tasks:
    asyncio.create_task(self._execute_task(task))
```

## Task Types

### Cron

Uses [croniter](https://github.com/kiorky/croniter) expressions:

```json
{
  "type": "cron",
  "value": "0 9 * * *"
}
```

Due when: current time >= next cron iteration after `last_run`.

### Interval

Seconds between runs:

```json
{
  "type": "interval",
  "value": "3600"
}
```

Due when: `(now - last_run).total_seconds() >= interval`. First run is immediate if no `last_run`.

### Once

ISO 8601 timestamp:

```json
{
  "type": "once",
  "value": "2025-06-15T10:00:00"
}
```

Due when: current time >= target timestamp. Automatically deactivated (`"active": false`) after execution.

## Task JSON Format

```json
{
  "id": "abc12345",
  "prompt": "Check the weather forecast for tomorrow",
  "type": "cron",
  "value": "0 9 * * *",
  "channel": "telegram",
  "chat_id": "123456789",
  "created_at": "2025-01-15T10:00:00+00:00",
  "last_run": null,
  "active": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Short UUID (first 8 chars) |
| `prompt` | `str` | Message sent to the agent when task fires |
| `type` | `str` | `"cron"`, `"interval"`, or `"once"` |
| `value` | `str` | Cron expression, seconds, or ISO timestamp |
| `channel` | `str` | Originating channel name |
| `chat_id` | `str` | Originating chat ID |
| `created_at` | `str` | ISO timestamp of creation |
| `last_run` | `str?` | ISO timestamp of last execution |
| `active` | `bool` | `false` = skipped by scheduler |

## Task Execution

Each due task runs as an independent `asyncio.Task`:

1. If the task has `model_tier`, calls `set_active_tier(tier)` so the `RoutingChatModel` uses that tier's LLM
2. Agent invoked with `thread_id = "scheduler_{task_id}"` — the agent runs with full tools, memory, and context on the specified tier
3. `reset_active_tier()` in a `finally` block ensures cleanup even on errors
4. Response extracted via `extract_agent_response()`
5. Result sent to the originating channel/chat via `channel.send()` with `disable_notification=True`
6. If channel/chat not available, result is logged and discarded

!!! info
    Scheduler tasks use their own thread IDs (`scheduler_*`), so they don't interfere with user conversation history.

### `model_tier` Field

Tasks can specify a `model_tier` to run on a specific LLM tier:

```json
{
  "id": "abc12345",
  "prompt": "Analyze my portfolio in depth",
  "type": "cron",
  "value": "0 9 * * *",
  "model_tier": "advanced"
}
```

When `model_tier` is set, the scheduler sets `_active_tier` before invoking the agent. Unlike the previous raw LLM approach, the agent runs with **all tools and memory** on the specified tier — it's the full agent, just on a different model.
