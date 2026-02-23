"""Tests for src.tools.cron — init_cron_tools, set_current_context, schedule/list/cancel tasks."""

import asyncio
import json

import pytest

from src.config import SchedulerConfig
from src.tools.cron import (
    init_cron_tools,
    set_current_context,
    get_tasks_lock,
    schedule_task,
    list_tasks,
    cancel_task,
    _current_channel,
    _current_chat_id,
)
from src.tools import cron as cron_module


class TestInitCronTools:
    def test_sets_data_file(self):
        config = SchedulerConfig(data_file="/tmp/tasks.json")
        init_cron_tools(config)
        assert cron_module._data_file == "/tmp/tasks.json"

    def test_default_data_file(self):
        config = SchedulerConfig()
        init_cron_tools(config)
        assert cron_module._data_file == "./data/scheduled_tasks.json"


class TestSetCurrentContext:
    def test_sets_context_vars(self):
        set_current_context("telegram", "12345")
        assert _current_channel.get() == "telegram"
        assert _current_chat_id.get() == "12345"

    def test_overwrite_context(self):
        set_current_context("telegram", "111")
        set_current_context("slack", "222")
        assert _current_channel.get() == "slack"
        assert _current_chat_id.get() == "222"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_cron(tmp_path, filename="tasks.json"):
    """Initialize cron tools pointing at a temp tasks file and return the path."""
    tasks_file = tmp_path / filename
    init_cron_tools(SchedulerConfig(data_file=str(tasks_file)))
    return tasks_file


# ---------------------------------------------------------------------------
# TestGetTasksLock
# ---------------------------------------------------------------------------

class TestGetTasksLock:
    def test_raises_when_not_initialized(self):
        cron_module._tasks_lock = None
        with pytest.raises(RuntimeError, match="not initialized"):
            get_tasks_lock()

    def test_returns_lock_after_init(self, tmp_path):
        _init_cron(tmp_path)
        lock = get_tasks_lock()
        assert isinstance(lock, asyncio.Lock)


# ---------------------------------------------------------------------------
# TestScheduleTask
# ---------------------------------------------------------------------------

class TestScheduleTask:
    @pytest.mark.asyncio
    async def test_valid_cron_task(self, tmp_path):
        tasks_file = _init_cron(tmp_path)
        set_current_context("telegram", "123")

        result = await schedule_task.ainvoke({
            "prompt": "say hello",
            "schedule_type": "cron",
            "schedule_value": "* * * * *",
        })

        assert "Task scheduled" in result
        assert "cron" in result
        data = json.loads(tasks_file.read_text())
        assert len(data) == 1
        assert data[0]["type"] == "cron"
        assert data[0]["value"] == "* * * * *"
        assert data[0]["prompt"] == "say hello"
        assert data[0]["channel"] == "telegram"
        assert data[0]["chat_id"] == "123"
        assert data[0]["active"] is True

    @pytest.mark.asyncio
    async def test_valid_interval_task(self, tmp_path):
        tasks_file = _init_cron(tmp_path)
        set_current_context("telegram", "456")

        result = await schedule_task.ainvoke({
            "prompt": "check status",
            "schedule_type": "interval",
            "schedule_value": "3600",
        })

        assert "Task scheduled" in result
        data = json.loads(tasks_file.read_text())
        assert len(data) == 1
        assert data[0]["type"] == "interval"
        assert data[0]["value"] == "3600"

    @pytest.mark.asyncio
    async def test_valid_once_task(self, tmp_path):
        tasks_file = _init_cron(tmp_path)
        set_current_context("telegram", "789")

        result = await schedule_task.ainvoke({
            "prompt": "one-shot reminder",
            "schedule_type": "once",
            "schedule_value": "2026-03-01T10:00:00Z",
        })

        assert "Task scheduled" in result
        data = json.loads(tasks_file.read_text())
        assert len(data) == 1
        assert data[0]["type"] == "once"

    @pytest.mark.asyncio
    async def test_invalid_type(self, tmp_path):
        _init_cron(tmp_path)
        set_current_context("telegram", "123")

        result = await schedule_task.ainvoke({
            "prompt": "bad task",
            "schedule_type": "invalid",
            "schedule_value": "whatever",
        })

        assert "Invalid schedule_type" in result


# ---------------------------------------------------------------------------
# TestListTasks
# ---------------------------------------------------------------------------

class TestListTasks:
    @pytest.mark.asyncio
    async def test_empty_file(self, tmp_path):
        tasks_file = _init_cron(tmp_path)
        tasks_file.write_text(json.dumps([]))

        result = await list_tasks.ainvoke({})
        assert "No active" in result

    @pytest.mark.asyncio
    async def test_with_active_tasks(self, tmp_path):
        tasks_file = _init_cron(tmp_path)
        tasks_data = [
            {
                "id": "abc",
                "prompt": "say hello every minute",
                "type": "cron",
                "value": "* * * * *",
                "channel": "telegram",
                "chat_id": "123",
                "created_at": "2026-01-01T00:00:00Z",
                "last_run": None,
                "active": True,
            },
            {
                "id": "def",
                "prompt": "inactive task",
                "type": "interval",
                "value": "60",
                "channel": "telegram",
                "chat_id": "123",
                "created_at": "2026-01-01T00:00:00Z",
                "last_run": None,
                "active": False,
            },
        ]
        tasks_file.write_text(json.dumps(tasks_data))

        result = await list_tasks.ainvoke({})
        assert "abc" in result
        assert "cron" in result
        assert "say hello" in result
        # Inactive task should NOT appear
        assert "def" not in result

    @pytest.mark.asyncio
    async def test_no_file(self, tmp_path):
        _init_cron(tmp_path, filename="nonexistent.json")
        # File does not exist on disk
        result = await list_tasks.ainvoke({})
        assert "No active" in result


# ---------------------------------------------------------------------------
# TestCancelTask
# ---------------------------------------------------------------------------

class TestCancelTask:
    @pytest.mark.asyncio
    async def test_cancel_found(self, tmp_path):
        tasks_file = _init_cron(tmp_path)
        tasks_data = [
            {
                "id": "abc",
                "prompt": "test task",
                "type": "cron",
                "value": "* * * * *",
                "channel": "telegram",
                "chat_id": "123",
                "created_at": "2026-01-01T00:00:00Z",
                "last_run": None,
                "active": True,
            },
        ]
        tasks_file.write_text(json.dumps(tasks_data))

        result = await cancel_task.ainvoke({"task_id": "abc"})
        assert "cancelled" in result

        updated = json.loads(tasks_file.read_text())
        assert updated[0]["active"] is False

    @pytest.mark.asyncio
    async def test_cancel_not_found(self, tmp_path):
        tasks_file = _init_cron(tmp_path)
        tasks_data = [
            {
                "id": "abc",
                "prompt": "test task",
                "type": "cron",
                "value": "* * * * *",
                "channel": "telegram",
                "chat_id": "123",
                "created_at": "2026-01-01T00:00:00Z",
                "last_run": None,
                "active": True,
            },
        ]
        tasks_file.write_text(json.dumps(tasks_data))

        result = await cancel_task.ainvoke({"task_id": "zzz"})
        assert "not found" in result
