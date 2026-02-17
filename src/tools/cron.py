"""Scheduled task tools - create, list, cancel tasks."""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

PROMPT_PREVIEW_LEN = 60

# Module-level config, set by init_cron_tools()
_data_file: str = "./data/scheduled_tasks.json"

# Set by router when handling a message, so schedule_task knows the origin
_current_channel: str | None = None
_current_chat_id: str | None = None


def init_cron_tools(config: dict) -> None:
    """Initialize cron tools with config."""
    global _data_file
    _data_file = config.get("scheduler", {}).get("data_file", "./data/scheduled_tasks.json")


def set_current_context(channel: str, chat_id: str) -> None:
    """Set the current channel/chat context for new tasks."""
    global _current_channel, _current_chat_id
    _current_channel = channel
    _current_chat_id = chat_id


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
def schedule_task(prompt: str, schedule_type: str, schedule_value: str) -> str:
    """Schedule a task to run later or on a recurring basis.

    Args:
        prompt: What the agent should do when the task runs.
        schedule_type: One of 'cron' (cron expression), 'interval' (seconds), 'once' (ISO timestamp).
        schedule_value: The schedule value matching the type.
    """
    if schedule_type not in ("cron", "interval", "once"):
        return f"Invalid schedule_type: {schedule_type}. Use 'cron', 'interval', or 'once'."

    task = {
        "id": str(uuid.uuid4())[:8],
        "prompt": prompt,
        "type": schedule_type,
        "value": schedule_value,
        "channel": _current_channel,
        "chat_id": _current_chat_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_run": None,
        "active": True,
    }

    tasks = _load_tasks()
    tasks.append(task)
    _save_tasks(tasks)

    logger.info("Scheduled task %s: %s (%s: %s) -> %s/%s",
                task["id"], prompt[:PROMPT_PREVIEW_LEN], schedule_type, schedule_value,
                _current_channel, _current_chat_id)
    return f"Task scheduled: id={task['id']}, type={schedule_type}, value={schedule_value}"


@tool
def list_tasks() -> str:
    """List all active scheduled tasks."""
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
def cancel_task(task_id: str) -> str:
    """Cancel a scheduled task by its ID."""
    tasks = _load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["active"] = False
            _save_tasks(tasks)
            logger.info("Cancelled task %s", task_id)
            return f"Task {task_id} cancelled."
    return f"Task {task_id} not found."
