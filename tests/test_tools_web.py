"""Tests for src.tools.web — init_web_tools sets module globals correctly."""

from src.config import WebConfig
from src.tools.web import init_web_tools
from src.tools import web as web_module


class TestInitWebTools:
    def test_sets_brave_api_key(self):
        config = WebConfig(brave_api_key="test-key", fetch_timeout=15)
        init_web_tools(config)
        assert web_module._brave_api_key == "test-key"
        assert web_module._fetch_timeout == 15

    def test_none_api_key(self):
        config = WebConfig(brave_api_key=None, fetch_timeout=30)
        init_web_tools(config)
        assert web_module._brave_api_key is None
        assert web_module._fetch_timeout == 30

    def test_empty_api_key_becomes_none(self):
        config = WebConfig(brave_api_key="")
        init_web_tools(config)
        assert web_module._brave_api_key is None

    def test_custom_timeout(self):
        config = WebConfig(fetch_timeout=60)
        init_web_tools(config)
        assert web_module._fetch_timeout == 60

    def test_default_config(self):
        config = WebConfig()
        init_web_tools(config)
        assert web_module._brave_api_key is None
        assert web_module._fetch_timeout == 30
