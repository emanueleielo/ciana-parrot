"""Scheduled task tools - create, list, cancel tasks."""

import asyncio
import json
import logging
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.tools import tool

from ..config import SchedulerConfig

logger = logging.getLogger(__name__)

PROMPT_PREVIEW_LEN = 60

# Module-level config, set by init_cron_tools()
_data_file: str = "./data/scheduled_tasks.json"

# Per-task context (propagated automatically by asyncio.create_task in Python 3.12+)
_current_channel: ContextVar[str | None] = ContextVar("_current_channel", default=None)
_current_chat_id: ContextVar[str | None] = ContextVar("_current_chat_id", default=None)

# Shared lock for read-modify-write on the tasks JSON file
_tasks_lock: asyncio.Lock | None = None


def get_tasks_lock() -> asyncio.Lock:
    """Return the shared lock for task file operations."""
    if _tasks_lock is None:
        raise RuntimeError("cron tools not initialized — call init_cron_tools() first")
    return _tasks_lock


def init_cron_tools(config: SchedulerConfig) -> None:
    """Initialize cron tools with config."""
    global _data_file, _tasks_lock
    _data_file = config.data_file
    _tasks_lock = asyncio.Lock()


def set_current_context(channel: str, chat_id: str) -> None:
    """Set the current channel/chat context for new tasks."""
    _current_channel.set(channel)
    _current_chat_id.set(chat_id)


def _load_tasks() -> list[dict]:
    path = Path(_data_file)
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def _save_tasks(tasks: list[dict]) -> None:
    path = Path(_data_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(tasks, f, indent=2)


@tool
async def schedule_task(prompt: str, schedule_type: str, schedule_value: str) -> str:
    """Schedule a task to run later or on a recurring basis.

    Args:
        prompt: What the agent should do when the task runs.
        schedule_type: One of 'cron' (cron expression), 'interval' (seconds), 'once' (ISO timestamp).
        schedule_value: The schedule value matching the type.
    """
    if schedule_type not in ("cron", "interval", "once"):
        return f"Invalid schedule_type: {schedule_type}. Use 'cron', 'interval', or 'once'."

    # Validate schedule_value based on type
    if schedule_type == "cron":
        try:
            from croniter import croniter
            croniter(schedule_value)
        except (ValueError, KeyError) as e:
            return f"Invalid cron expression '{schedule_value}': {e}"
    elif schedule_type == "interval":
        try:
            interval = int(schedule_value)
            if interval <= 0:
                return f"Invalid interval: must be a positive number of seconds, got '{schedule_value}'."
        except ValueError:
            return f"Invalid interval: '{schedule_value}' is not a valid integer."
    elif schedule_type == "once":
        try:
            datetime.fromisoformat(schedule_value)
        except ValueError:
            return f"Invalid ISO timestamp: '{schedule_value}'. Use format like '2025-01-15T10:00:00'."

    channel = _current_channel.get()
    chat_id = _current_chat_id.get()

    task = {
        "id": str(uuid.uuid4())[:8],
        "prompt": prompt,
        "type": schedule_type,
        "value": schedule_value,
        "channel": channel,
        "chat_id": chat_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_run": None,
        "active": True,
    }

    async with _tasks_lock:
        tasks = _load_tasks()
        tasks.append(task)
        _save_tasks(tasks)

    logger.info("Scheduled task %s: %s (%s: %s) -> %s/%s",
                task["id"], prompt[:PROMPT_PREVIEW_LEN], schedule_type, schedule_value,
                channel, chat_id)
    return f"Task scheduled: id={task['id']}, type={schedule_type}, value={schedule_value}"


@tool
async def list_tasks() -> str:
    """List all active scheduled tasks."""
    async with _tasks_lock:
        tasks = _load_tasks()
    active = [t for t in tasks if t.get("active", True)]
    if not active:
        return "No active scheduled tasks."

    lines = []
    for t in active:
        lines.append(
            f"- [{t['id']}] {t['type']}={t['value']} | {t['prompt'][:PROMPT_PREVIEW_LEN]}"
            f" | last_run={t.get('last_run', 'never')}"
        )
    return "\n".join(lines)


@tool
async def cancel_task(task_id: str) -> str:
    """Cancel a scheduled task by its ID."""
    async with _tasks_lock:
        tasks = _load_tasks()
        for t in tasks:
            if t["id"] == task_id:
                t["active"] = False
                _save_tasks(tasks)
                logger.info("Cancelled task %s", task_id)
                return f"Task {task_id} cancelled."
    return f"Task {task_id} not found."
