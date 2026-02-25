"""Tests for src.scheduler — _is_due, _check_and_run, _execute_task, start/stop."""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import AppConfig, SchedulerConfig
from src.tools.model_router import _active_tier, init_model_router_tools
from src.scheduler import Scheduler


@pytest.fixture
def scheduler(mock_agent, tmp_path) -> Scheduler:
    config = AppConfig(
        scheduler=SchedulerConfig(data_file=str(tmp_path / "tasks.json")),
    )
    return Scheduler(mock_agent, config)


class TestIsDueOnce:
    def test_future_task(self, scheduler):
        now = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        task = {"type": "once", "value": "2025-06-02T00:00:00+00:00", "last_run": None}
        assert scheduler._is_due(task, now) is False

    def test_past_task(self, scheduler):
        now = datetime(2025, 6, 2, 12, 0, tzinfo=timezone.utc)
        task = {"type": "once", "value": "2025-06-01T00:00:00+00:00", "last_run": None}
        assert scheduler._is_due(task, now) is True

    def test_already_run(self, scheduler):
        now = datetime(2025, 6, 2, 12, 0, tzinfo=timezone.utc)
        task = {
            "type": "once",
            "value": "2025-06-01T00:00:00+00:00",
            "last_run": "2025-06-01T00:01:00+00:00",
        }
        assert scheduler._is_due(task, now) is False

    def test_exact_time(self, scheduler):
        now = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        task = {"type": "once", "value": "2025-06-01T12:00:00+00:00", "last_run": None}
        assert scheduler._is_due(task, now) is True

    def test_invalid_timestamp(self, scheduler):
        now = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        task = {"type": "once", "value": "not-a-date", "last_run": None}
        assert scheduler._is_due(task, now) is False

    def test_naive_timestamp_assumed_utc(self, scheduler):
        now = datetime(2025, 6, 2, 12, 0, tzinfo=timezone.utc)
        task = {"type": "once", "value": "2025-06-01T00:00:00", "last_run": None}
        assert scheduler._is_due(task, now) is True


class TestIsDueInterval:
    def test_never_run(self, scheduler):
        now = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        task = {"type": "interval", "value": "3600", "last_run": None}
        assert scheduler._is_due(task, now) is True

    def test_interval_elapsed(self, scheduler):
        now = datetime(2025, 6, 1, 13, 0, 1, tzinfo=timezone.utc)
        task = {
            "type": "interval",
            "value": "3600",
            "last_run": "2025-06-01T12:00:00+00:00",
        }
        assert scheduler._is_due(task, now) is True

    def test_interval_not_elapsed(self, scheduler):
        now = datetime(2025, 6, 1, 12, 30, tzinfo=timezone.utc)
        task = {
            "type": "interval",
            "value": "3600",
            "last_run": "2025-06-01T12:00:00+00:00",
        }
        assert scheduler._is_due(task, now) is False

    def test_exact_interval(self, scheduler):
        now = datetime(2025, 6, 1, 13, 0, 0, tzinfo=timezone.utc)
        task = {
            "type": "interval",
            "value": "3600",
            "last_run": "2025-06-01T12:00:00+00:00",
        }
        assert scheduler._is_due(task, now) is True

    def test_invalid_interval(self, scheduler):
        now = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        task = {"type": "interval", "value": "abc", "last_run": None}
        assert scheduler._is_due(task, now) is False


class TestIsDueCron:
    def test_never_run(self, scheduler):
        now = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        task = {"type": "cron", "value": "*/5 * * * *", "last_run": None}
        assert scheduler._is_due(task, now) is True

    def test_cron_due(self, scheduler):
        now = datetime(2025, 6, 1, 12, 10, tzinfo=timezone.utc)
        task = {
            "type": "cron",
            "value": "*/5 * * * *",
            "last_run": "2025-06-01T12:00:00+00:00",
        }
        assert scheduler._is_due(task, now) is True

    def test_cron_not_due(self, scheduler):
        now = datetime(2025, 6, 1, 12, 3, tzinfo=timezone.utc)
        task = {
            "type": "cron",
            "value": "*/5 * * * *",
            "last_run": "2025-06-01T12:00:00+00:00",
        }
        assert scheduler._is_due(task, now) is False

    def test_invalid_cron(self, scheduler):
        now = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        task = {"type": "cron", "value": "not a cron", "last_run": None}
        # Never-run cron returns True even with invalid expression
        # because the check short-circuits before parsing
        assert scheduler._is_due(task, now) is True

    def test_invalid_cron_with_last_run(self, scheduler):
        now = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        task = {
            "type": "cron",
            "value": "not a cron",
            "last_run": "2025-06-01T11:00:00+00:00",
        }
        assert scheduler._is_due(task, now) is False


class TestIsDueUnknownType:
    def test_unknown_type(self, scheduler):
        now = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        task = {"type": "unknown", "value": "x"}
        assert scheduler._is_due(task, now) is False


# ---------------------------------------------------------------------------
# Fixture for tests that need the asyncio tasks lock initialized
# ---------------------------------------------------------------------------

@pytest.fixture
def scheduler_with_lock(mock_agent, tmp_path):
    """Scheduler with init_cron_tools() called so get_tasks_lock() works."""
    from src.tools.cron import init_cron_tools

    config = AppConfig(
        scheduler=SchedulerConfig(
            data_file=str(tmp_path / "tasks.json"),
            poll_interval=1,
        ),
    )
    init_cron_tools(config.scheduler)
    return Scheduler(mock_agent, config)


def _write_tasks(path, tasks):
    """Helper: write a tasks JSON list to *path*."""
    with open(path, "w") as f:
        json.dump(tasks, f, indent=2)


def _read_tasks(path):
    """Helper: read tasks JSON list from *path*."""
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# TestCheckAndRun
# ---------------------------------------------------------------------------

class TestCheckAndRun:
    """Tests for Scheduler._check_and_run()."""

    @pytest.mark.asyncio
    async def test_no_file_returns_early(self, scheduler_with_lock, mock_agent):
        """When the tasks file doesn't exist, _check_and_run returns without error."""
        await scheduler_with_lock._check_and_run()
        mock_agent.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_reads_and_marks_due_task(self, scheduler_with_lock, tmp_path, mock_agent):
        """A due 'once' task gets last_run set and active=False."""
        tasks_path = tmp_path / "tasks.json"
        _write_tasks(tasks_path, [
            {
                "id": "t1",
                "prompt": "do something",
                "type": "once",
                "value": "2020-01-01T00:00:00+00:00",
                "last_run": None,
                "active": True,
                "channel": "telegram",
                "chat_id": "123",
            }
        ])

        await scheduler_with_lock._check_and_run()
        # Allow spawned tasks to finish
        await asyncio.sleep(0.05)

        updated = _read_tasks(tasks_path)
        assert updated[0]["last_run"] is not None
        assert updated[0]["active"] is False

    @pytest.mark.asyncio
    async def test_skips_inactive_task(self, scheduler_with_lock, tmp_path, mock_agent):
        """Inactive tasks should not trigger agent invocation."""
        tasks_path = tmp_path / "tasks.json"
        _write_tasks(tasks_path, [
            {
                "id": "t2",
                "prompt": "inactive task",
                "type": "once",
                "value": "2020-01-01T00:00:00+00:00",
                "last_run": None,
                "active": False,
                "channel": "telegram",
                "chat_id": "123",
            }
        ])

        await scheduler_with_lock._check_and_run()
        await asyncio.sleep(0.05)

        mock_agent.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_cron_task_stays_active(self, scheduler_with_lock, tmp_path, mock_agent):
        """A due cron task gets last_run set but stays active=True."""
        tasks_path = tmp_path / "tasks.json"
        _write_tasks(tasks_path, [
            {
                "id": "t3",
                "prompt": "cron job",
                "type": "cron",
                "value": "*/5 * * * *",
                "last_run": None,
                "active": True,
                "channel": "telegram",
                "chat_id": "123",
            }
        ])

        await scheduler_with_lock._check_and_run()
        await asyncio.sleep(0.05)

        updated = _read_tasks(tasks_path)
        assert updated[0]["active"] is True
        assert updated[0]["last_run"] is not None

    @pytest.mark.asyncio
    async def test_spawns_execute_for_due_tasks(self, scheduler_with_lock, tmp_path):
        """Two due tasks should both be dispatched for execution."""
        tasks_path = tmp_path / "tasks.json"
        _write_tasks(tasks_path, [
            {
                "id": "ta",
                "prompt": "task a",
                "type": "once",
                "value": "2020-01-01T00:00:00+00:00",
                "last_run": None,
                "active": True,
                "channel": "telegram",
                "chat_id": "1",
            },
            {
                "id": "tb",
                "prompt": "task b",
                "type": "once",
                "value": "2020-01-01T00:00:00+00:00",
                "last_run": None,
                "active": True,
                "channel": "telegram",
                "chat_id": "2",
            },
        ])

        with patch.object(scheduler_with_lock, "_execute_task", new_callable=AsyncMock) as mock_exec:
            await scheduler_with_lock._check_and_run()
            # Yield control so create_task callbacks fire
            await asyncio.sleep(0.05)

            assert mock_exec.call_count == 2
            called_ids = {call.args[0]["id"] for call in mock_exec.call_args_list}
            assert called_ids == {"ta", "tb"}

    @pytest.mark.asyncio
    async def test_no_due_tasks_no_modifications(self, scheduler_with_lock, tmp_path):
        """Tasks with future timestamps should not be modified."""
        tasks_path = tmp_path / "tasks.json"
        original = [
            {
                "id": "tf",
                "prompt": "future task",
                "type": "once",
                "value": "2099-12-31T23:59:59+00:00",
                "last_run": None,
                "active": True,
                "channel": "telegram",
                "chat_id": "123",
            }
        ]
        _write_tasks(tasks_path, original)

        await scheduler_with_lock._check_and_run()

        updated = _read_tasks(tasks_path)
        assert updated == original


# ---------------------------------------------------------------------------
# TestExecuteTask
# ---------------------------------------------------------------------------

class TestExecuteTask:
    """Tests for Scheduler._execute_task()."""

    @pytest.mark.asyncio
    async def test_success_sends_to_channel(self, mock_agent, tmp_path):
        """Successful execution sends the result to the correct channel/chat."""
        from src.tools.cron import init_cron_tools

        config = AppConfig(
            scheduler=SchedulerConfig(
                data_file=str(tmp_path / "tasks.json"),
                poll_interval=1,
            ),
        )
        init_cron_tools(config.scheduler)

        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()

        sched = Scheduler(mock_agent, config, channels={"telegram": mock_channel})

        task = {
            "id": "ex1",
            "prompt": "run something",
            "type": "once",
            "value": "2020-01-01T00:00:00+00:00",
            "last_run": None,
            "active": True,
            "channel": "telegram",
            "chat_id": "456",
        }

        await sched._execute_task(task)

        mock_agent.ainvoke.assert_called_once()
        mock_channel.send.assert_called_once()
        call_args = mock_channel.send.call_args
        assert call_args[0][0] == "456"  # chat_id is the first positional arg

    @pytest.mark.asyncio
    async def test_missing_channel(self, mock_agent, tmp_path):
        """Task referencing a non-existent channel should not raise."""
        from src.tools.cron import init_cron_tools

        config = AppConfig(
            scheduler=SchedulerConfig(
                data_file=str(tmp_path / "tasks.json"),
                poll_interval=1,
            ),
        )
        init_cron_tools(config.scheduler)

        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()

        sched = Scheduler(mock_agent, config, channels={"telegram": mock_channel})

        task = {
            "id": "ex2",
            "prompt": "unknown channel task",
            "type": "once",
            "value": "2020-01-01T00:00:00+00:00",
            "last_run": None,
            "active": True,
            "channel": "unknown",
            "chat_id": "789",
        }

        # Should not raise
        await sched._execute_task(task)
        mock_channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_channel_in_task(self, mock_agent, tmp_path):
        """Task with no channel key should not raise."""
        from src.tools.cron import init_cron_tools

        config = AppConfig(
            scheduler=SchedulerConfig(
                data_file=str(tmp_path / "tasks.json"),
                poll_interval=1,
            ),
        )
        init_cron_tools(config.scheduler)

        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()

        sched = Scheduler(mock_agent, config, channels={"telegram": mock_channel})

        task = {
            "id": "ex3",
            "prompt": "no channel",
            "type": "once",
            "value": "2020-01-01T00:00:00+00:00",
            "last_run": None,
            "active": True,
        }

        # Should not raise
        await sched._execute_task(task)
        mock_channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_agent_error(self, mock_agent, tmp_path):
        """Agent exception should be caught and logged, not propagated."""
        from src.tools.cron import init_cron_tools

        config = AppConfig(
            scheduler=SchedulerConfig(
                data_file=str(tmp_path / "tasks.json"),
                poll_interval=1,
            ),
        )
        init_cron_tools(config.scheduler)

        mock_agent.ainvoke.side_effect = Exception("boom")

        sched = Scheduler(mock_agent, config)

        task = {
            "id": "ex4",
            "prompt": "will fail",
            "type": "once",
            "value": "2020-01-01T00:00:00+00:00",
            "last_run": None,
            "active": True,
            "channel": "telegram",
            "chat_id": "123",
        }

        # Should not propagate
        await sched._execute_task(task)

    @pytest.mark.asyncio
    async def test_sends_with_disable_notification(self, mock_agent, tmp_path):
        """Channel.send should be called with disable_notification=True."""
        from src.tools.cron import init_cron_tools

        config = AppConfig(
            scheduler=SchedulerConfig(
                data_file=str(tmp_path / "tasks.json"),
                poll_interval=1,
            ),
        )
        init_cron_tools(config.scheduler)

        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()

        sched = Scheduler(mock_agent, config, channels={"telegram": mock_channel})

        task = {
            "id": "ex5",
            "prompt": "notify test",
            "type": "once",
            "value": "2020-01-01T00:00:00+00:00",
            "last_run": None,
            "active": True,
            "channel": "telegram",
            "chat_id": "555",
        }

        await sched._execute_task(task)

        mock_channel.send.assert_called_once()
        call_kwargs = mock_channel.send.call_args[1]
        assert call_kwargs.get("disable_notification") is True


# ---------------------------------------------------------------------------
# TestSchedulerLifecycle
# ---------------------------------------------------------------------------

class TestSchedulerLifecycle:
    """Tests for Scheduler.start() and stop()."""

    @pytest.mark.asyncio
    async def test_start_creates_task(self, scheduler_with_lock):
        """start() should create an internal asyncio task."""
        await scheduler_with_lock.start()
        assert scheduler_with_lock._task is not None
        assert scheduler_with_lock._running is True
        await scheduler_with_lock.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self, scheduler_with_lock):
        """stop() should set _running to False and cancel the loop task."""
        await scheduler_with_lock.start()
        assert scheduler_with_lock._running is True
        await scheduler_with_lock.stop()
        assert scheduler_with_lock._running is False

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self, scheduler_with_lock):
        """stop() without start() should not raise."""
        await scheduler_with_lock.stop()
        assert scheduler_with_lock._running is False


# ---------------------------------------------------------------------------
# TestOnceTaskAutoDeactivation
# ---------------------------------------------------------------------------

class TestOnceTaskAutoDeactivation:
    """Verify that 'once' tasks deactivate while recurring tasks stay active."""

    @pytest.mark.asyncio
    async def test_once_task_deactivated_after_run(self, scheduler_with_lock, tmp_path):
        """A due 'once' task should have active=False after _check_and_run."""
        tasks_path = tmp_path / "tasks.json"
        _write_tasks(tasks_path, [
            {
                "id": "once1",
                "prompt": "one-shot task",
                "type": "once",
                "value": "2020-01-01T00:00:00+00:00",
                "last_run": None,
                "active": True,
                "channel": "telegram",
                "chat_id": "123",
            }
        ])

        await scheduler_with_lock._check_and_run()
        await asyncio.sleep(0.05)

        updated = _read_tasks(tasks_path)
        assert updated[0]["active"] is False
        assert updated[0]["last_run"] is not None

    @pytest.mark.asyncio
    async def test_interval_task_stays_active_after_run(self, scheduler_with_lock, tmp_path):
        """A due 'interval' task should remain active=True with last_run set."""
        tasks_path = tmp_path / "tasks.json"
        _write_tasks(tasks_path, [
            {
                "id": "int1",
                "prompt": "recurring task",
                "type": "interval",
                "value": "60",
                "last_run": None,
                "active": True,
                "channel": "telegram",
                "chat_id": "123",
            }
        ])

        await scheduler_with_lock._check_and_run()
        await asyncio.sleep(0.05)

        updated = _read_tasks(tasks_path)
        assert updated[0]["active"] is True
        assert updated[0]["last_run"] is not None


# ---------------------------------------------------------------------------
# TestSchedulerTierExecution
# ---------------------------------------------------------------------------

class TestSchedulerTierExecution:
    """Tests for tier-based execution via _active_tier in _execute_task."""

    @pytest.mark.asyncio
    async def test_task_with_tier_sets_active_tier(self, tmp_path):
        """A task with model_tier should set _active_tier before agent.ainvoke."""
        from src.tools.cron import init_cron_tools

        config = AppConfig(
            scheduler=SchedulerConfig(data_file=str(tmp_path / "tasks.json")),
        )
        init_cron_tools(config.scheduler)

        captured_tier = []

        async def capture_tier(*args, **kwargs):
            captured_tier.append(_active_tier.get())
            mock_msg = MagicMock(type="ai", content="Tier response", tool_calls=[])
            return {"messages": [mock_msg]}

        main_agent = AsyncMock()
        main_agent.ainvoke.side_effect = capture_tier

        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()

        sched = Scheduler(main_agent, config, channels={"telegram": mock_channel})

        task = {
            "id": "t1",
            "prompt": "quick check",
            "type": "once",
            "value": "2020-01-01T00:00:00+00:00",
            "last_run": None,
            "active": True,
            "channel": "telegram",
            "chat_id": "123",
            "model_tier": "lite",
        }

        await sched._execute_task(task)

        # Tier was set during ainvoke
        assert captured_tier == ["lite"]
        # Tier is reset after execution
        assert _active_tier.get() is None
        main_agent.ainvoke.assert_called_once()
        mock_channel.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_task_without_tier_uses_agent(self, tmp_path):
        """A task without model_tier should use the full agent without setting tier."""
        from src.tools.cron import init_cron_tools

        config = AppConfig(
            scheduler=SchedulerConfig(data_file=str(tmp_path / "tasks.json")),
        )
        init_cron_tools(config.scheduler)

        main_agent = AsyncMock()
        mock_msg = MagicMock(type="ai", content="Agent response", tool_calls=[])
        main_agent.ainvoke.return_value = {"messages": [mock_msg]}

        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()

        sched = Scheduler(main_agent, config, channels={"telegram": mock_channel})

        task = {
            "id": "t2",
            "prompt": "complex task",
            "type": "once",
            "value": "2020-01-01T00:00:00+00:00",
            "last_run": None,
            "active": True,
            "channel": "telegram",
            "chat_id": "456",
        }

        await sched._execute_task(task)

        main_agent.ainvoke.assert_called_once()
        # No tier was set
        assert _active_tier.get() is None

    @pytest.mark.asyncio
    async def test_tier_reset_on_agent_error(self, tmp_path):
        """_active_tier should be reset even if agent.ainvoke raises."""
        from src.tools.cron import init_cron_tools

        config = AppConfig(
            scheduler=SchedulerConfig(data_file=str(tmp_path / "tasks.json")),
        )
        init_cron_tools(config.scheduler)

        main_agent = AsyncMock()
        main_agent.ainvoke.side_effect = RuntimeError("boom")

        sched = Scheduler(main_agent, config)

        task = {
            "id": "t3",
            "prompt": "will fail",
            "type": "once",
            "value": "2020-01-01T00:00:00+00:00",
            "last_run": None,
            "active": True,
            "channel": "telegram",
            "chat_id": "789",
            "model_tier": "expert",
        }

        # Should not propagate
        await sched._execute_task(task)

        # Tier is reset despite the error
        assert _active_tier.get() is None
