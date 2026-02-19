"""Task scheduler - runs cron/interval/once tasks via the agent."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from croniter import croniter

from .agent_response import extract_agent_response
from .config import AppConfig
from .tools.cron import get_tasks_lock

logger = logging.getLogger(__name__)


class Scheduler:
    """Polls scheduled_tasks.json and executes due tasks."""

    def __init__(self, agent, config: AppConfig, channels: dict = None):
        self._agent = agent
        self._config = config
        self._poll_interval = config.scheduler.poll_interval
        self._data_file = config.scheduler.data_file
        self._channels = channels or {}  # name -> channel instance
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the scheduler loop."""
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Scheduler started (poll every %ds)", self._poll_interval)

    async def stop(self) -> None:
        """Stop the scheduler loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")

    async def _loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                await self._check_and_run()
            except (json.JSONDecodeError, OSError) as e:
                logger.error("Scheduler failed to read tasks file: %s", e)
            except Exception:
                logger.exception("Scheduler check error")
            await asyncio.sleep(self._poll_interval)

    async def _check_and_run(self) -> None:
        """Check for due tasks and run them.

        The check phase (read + mark due + write) runs under the shared
        tasks lock so cron tool mutations don't race.  Execution happens
        outside the lock via parallel create_task calls.
        """
        path = Path(self._data_file)
        if not path.exists():
            return

        due_tasks: list[dict] = []

        async with get_tasks_lock():
            with open(path) as f:
                tasks = json.load(f)

            now = datetime.now(timezone.utc)
            modified = False

            for task in tasks:
                if not task.get("active", True):
                    continue
                if self._is_due(task, now):
                    task["last_run"] = now.isoformat()
                    if task["type"] == "once":
                        task["active"] = False
                    modified = True
                    due_tasks.append(dict(task))  # snapshot for execution

            if modified:
                with open(path, "w") as f:
                    json.dump(tasks, f, indent=2)

        # Execute due tasks in parallel, outside the lock
        for task in due_tasks:
            logger.info("Running scheduled task: %s", task["id"])
            asyncio.create_task(self._execute_task(task))

    def _is_due(self, task: dict, now: datetime) -> bool:
        """Check if a task is due to run."""
        last_run = task.get("last_run")

        if task["type"] == "once":
            if last_run:
                return False
            try:
                target = datetime.fromisoformat(task["value"])
                if target.tzinfo is None:
                    target = target.replace(tzinfo=timezone.utc)
                return now >= target
            except ValueError:
                logger.warning("Invalid once timestamp: %s", task["value"])
                return False

        elif task["type"] == "interval":
            try:
                interval = int(task["value"])
            except ValueError:
                logger.warning("Invalid interval: %s", task["value"])
                return False
            if not last_run:
                return True
            last = datetime.fromisoformat(last_run)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            return (now - last).total_seconds() >= interval

        elif task["type"] == "cron":
            if not last_run:
                return True
            try:
                last = datetime.fromisoformat(last_run)
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                cron = croniter(task["value"], last)
                next_run = cron.get_next(datetime)
                if next_run.tzinfo is None:
                    next_run = next_run.replace(tzinfo=timezone.utc)
                return now >= next_run
            except (KeyError, ValueError, TypeError):
                logger.warning("Invalid cron expression: %s", task["value"])
                return False

        return False

    async def _execute_task(self, task: dict) -> None:
        """Execute a scheduled task and send the result to the originating channel."""
        thread_id = f"scheduler_{task['id']}"
        try:
            result = await self._agent.ainvoke(
                {"messages": [{"role": "user", "content": task["prompt"]}]},
                config={"configurable": {"thread_id": thread_id}},
            )
            agent_resp = extract_agent_response(result)
            response = agent_resp.text

            # Send result to the channel that created the task
            channel_name = task.get("channel")
            chat_id = task.get("chat_id")
            if channel_name and chat_id and channel_name in self._channels:
                channel = self._channels[channel_name]
                await channel.send(chat_id, response, disable_notification=True)
                logger.info("Scheduler sent result to %s/%s", channel_name, chat_id)
            else:
                logger.warning("Task %s has no valid channel/chat_id, result discarded", task["id"])

        except Exception:
            logger.exception("Failed to execute task %s", task["id"])
