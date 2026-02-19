"""Tests for src.scheduler — _is_due for cron/interval/once."""

from datetime import datetime, timezone, timedelta

import pytest

from src.config import AppConfig, SchedulerConfig
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
