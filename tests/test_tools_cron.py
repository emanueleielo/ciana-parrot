"""Tests for src.tools.cron — init_cron_tools, set_current_context."""

from src.config import SchedulerConfig
from src.tools.cron import init_cron_tools, set_current_context, _current_channel, _current_chat_id
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
