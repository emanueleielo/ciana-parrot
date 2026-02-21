"""Tests for src.config — env expansion, validation, load_config."""

import json

import pytest
from pydantic import ValidationError

from src.config import (
    AppConfig,
    AgentConfig,
    ChannelsConfig,
    ClaudeCodeConfig,
    LoggingConfig,
    ProviderConfig,
    SchedulerConfig,
    TelegramChannelConfig,
    TranscriptionConfig,
    WebConfig,
    _expand_env,
    _walk_expand,
    load_config,
)


# --- _expand_env ---

class TestExpandEnv:
    def test_simple_var(self, monkeypatch):
        monkeypatch.setenv("FOO", "bar")
        assert _expand_env("${FOO}") == "bar"

    def test_missing_var_returns_empty(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT", raising=False)
        assert _expand_env("${NONEXISTENT}") == ""

    def test_multiple_vars(self, monkeypatch):
        monkeypatch.setenv("A", "hello")
        monkeypatch.setenv("B", "world")
        assert _expand_env("${A} ${B}") == "hello world"

    def test_no_vars(self):
        assert _expand_env("plain text") == "plain text"

    def test_mixed_content(self, monkeypatch):
        monkeypatch.setenv("KEY", "secret")
        assert _expand_env("prefix-${KEY}-suffix") == "prefix-secret-suffix"

    def test_empty_string(self):
        assert _expand_env("") == ""


# --- _walk_expand ---

class TestWalkExpand:
    def test_nested_dict(self, monkeypatch):
        monkeypatch.setenv("X", "val")
        result = _walk_expand({"a": {"b": "${X}"}})
        assert result == {"a": {"b": "val"}}

    def test_list(self, monkeypatch):
        monkeypatch.setenv("Y", "item")
        result = _walk_expand(["${Y}", "static"])
        assert result == ["item", "static"]

    def test_non_string_passthrough(self):
        assert _walk_expand(42) == 42
        assert _walk_expand(True) is True
        assert _walk_expand(None) is None

    def test_deeply_nested(self, monkeypatch):
        monkeypatch.setenv("Z", "deep")
        result = _walk_expand({"a": [{"b": "${Z}"}]})
        assert result == {"a": [{"b": "deep"}]}


# --- Pydantic model validation ---

class TestProviderConfig:
    def test_defaults(self):
        cfg = ProviderConfig()
        assert cfg.name == "anthropic"
        assert cfg.model == "claude-sonnet-4-6"
        assert cfg.temperature is None

    def test_temperature_valid(self):
        cfg = ProviderConfig(temperature=0.5)
        assert cfg.temperature == 0.5

    def test_temperature_zero(self):
        cfg = ProviderConfig(temperature=0)
        assert cfg.temperature == 0.0

    def test_temperature_max(self):
        cfg = ProviderConfig(temperature=2.0)
        assert cfg.temperature == 2.0

    def test_temperature_out_of_range(self):
        with pytest.raises(ValidationError, match="temperature"):
            ProviderConfig(temperature=3.0)

    def test_temperature_negative(self):
        with pytest.raises(ValidationError, match="temperature"):
            ProviderConfig(temperature=-0.1)

    def test_api_key_empty_to_none(self):
        cfg = ProviderConfig(api_key="")
        assert cfg.api_key is None

    def test_api_key_whitespace_to_none(self):
        cfg = ProviderConfig(api_key="  ")
        assert cfg.api_key is None

    def test_api_key_value_kept(self):
        cfg = ProviderConfig(api_key="sk-123")
        assert cfg.api_key == "sk-123"

    def test_base_url_empty_to_none(self):
        cfg = ProviderConfig(base_url="")
        assert cfg.base_url is None


class TestTelegramChannelConfig:
    def test_defaults(self):
        cfg = TelegramChannelConfig()
        assert cfg.enabled is False
        assert cfg.trigger == "@Ciana"
        assert cfg.allowed_users == []

    def test_allowed_users_int_coercion(self):
        cfg = TelegramChannelConfig(allowed_users=[123, 456])
        assert cfg.allowed_users == ["123", "456"]

    def test_allowed_users_mixed(self):
        cfg = TelegramChannelConfig(allowed_users=["abc", 789])
        assert cfg.allowed_users == ["abc", "789"]


class TestSchedulerConfig:
    def test_defaults(self):
        cfg = SchedulerConfig()
        assert cfg.poll_interval == 60
        assert cfg.enabled is False

    def test_poll_interval_valid(self):
        cfg = SchedulerConfig(poll_interval=5)
        assert cfg.poll_interval == 5

    def test_poll_interval_zero_invalid(self):
        with pytest.raises(ValidationError, match="poll_interval"):
            SchedulerConfig(poll_interval=0)

    def test_poll_interval_negative_invalid(self):
        with pytest.raises(ValidationError, match="poll_interval"):
            SchedulerConfig(poll_interval=-1)


class TestWebConfig:
    def test_brave_api_key_empty_to_none(self):
        cfg = WebConfig(brave_api_key="")
        assert cfg.brave_api_key is None

    def test_brave_api_key_value_kept(self):
        cfg = WebConfig(brave_api_key="bk-123")
        assert cfg.brave_api_key == "bk-123"

    def test_default_timeout(self):
        cfg = WebConfig()
        assert cfg.fetch_timeout == 30


class TestTranscriptionConfig:
    def test_defaults(self):
        cfg = TranscriptionConfig()
        assert cfg.enabled is False
        assert cfg.provider == "groq"
        assert cfg.model == "whisper-large-v3-turbo"
        assert cfg.api_key is None
        assert cfg.base_url is None
        assert cfg.timeout == 30

    def test_api_key_empty_to_none(self):
        cfg = TranscriptionConfig(api_key="")
        assert cfg.api_key is None

    def test_api_key_whitespace_to_none(self):
        cfg = TranscriptionConfig(api_key="  ")
        assert cfg.api_key is None

    def test_api_key_value_kept(self):
        cfg = TranscriptionConfig(api_key="gsk_test")
        assert cfg.api_key == "gsk_test"

    def test_base_url_empty_to_none(self):
        cfg = TranscriptionConfig(base_url="")
        assert cfg.base_url is None

    def test_valid_providers(self):
        for provider in ("groq", "openai"):
            cfg = TranscriptionConfig(provider=provider)
            assert cfg.provider == provider

    def test_invalid_provider(self):
        with pytest.raises(ValidationError, match="transcription provider"):
            TranscriptionConfig(provider="invalid")


class TestClaudeCodeConfig:
    def test_bridge_token_empty_to_none(self):
        cfg = ClaudeCodeConfig(bridge_token="")
        assert cfg.bridge_token is None

    def test_bridge_url_empty_to_none(self):
        cfg = ClaudeCodeConfig(bridge_url="")
        assert cfg.bridge_url is None

    def test_permission_mode_empty_to_none(self):
        cfg = ClaudeCodeConfig(permission_mode="")
        assert cfg.permission_mode is None

    def test_defaults(self):
        cfg = ClaudeCodeConfig()
        assert cfg.bridge_port == 9842
        assert cfg.timeout == 0
        assert cfg.claude_path == "claude"


class TestLoggingConfig:
    def test_uppercase_normalization(self):
        cfg = LoggingConfig(level="debug")
        assert cfg.level == "DEBUG"

    def test_valid_levels(self):
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            cfg = LoggingConfig(level=level)
            assert cfg.level == level

    def test_invalid_level(self):
        with pytest.raises(ValidationError, match="logging level"):
            LoggingConfig(level="VERBOSE")


class TestAppConfig:
    def test_all_defaults(self):
        cfg = AppConfig()
        assert cfg.agent.workspace == "./workspace"
        assert cfg.provider.name == "anthropic"
        assert cfg.channels.telegram.enabled is False
        assert cfg.mcp_servers == {}

    def test_partial_override(self):
        cfg = AppConfig(agent=AgentConfig(workspace="/tmp/ws"))
        assert cfg.agent.workspace == "/tmp/ws"
        assert cfg.provider.name == "anthropic"  # default preserved

    def test_model_validate_from_dict(self):
        data = {
            "agent": {"workspace": "/custom"},
            "provider": {"name": "openai", "model": "gpt-4"},
        }
        cfg = AppConfig.model_validate(data)
        assert cfg.agent.workspace == "/custom"
        assert cfg.provider.name == "openai"
        assert cfg.scheduler.enabled is False  # default


# --- load_config ---

class TestLoadConfig:
    def test_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.yaml")

    def test_minimal_yaml(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("agent:\n  workspace: /tmp/test\n")
        cfg = load_config(str(cfg_file))
        assert cfg.agent.workspace == "/tmp/test"
        assert cfg.provider.name == "anthropic"

    def test_env_expansion_in_yaml(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MY_TOKEN", "tok-abc")
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "channels:\n"
            "  telegram:\n"
            "    token: '${MY_TOKEN}'\n"
            "    enabled: true\n"
        )
        cfg = load_config(str(cfg_file))
        assert cfg.channels.telegram.token == "tok-abc"

    def test_empty_yaml(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("")
        cfg = load_config(str(cfg_file))
        assert isinstance(cfg, AppConfig)

    def test_full_config(self, tmp_path, monkeypatch):
        monkeypatch.setenv("API_KEY", "key123")
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(json.dumps({
            "agent": {"workspace": "/app/ws"},
            "provider": {"name": "openai", "model": "gpt-4", "api_key": "${API_KEY}"},
            "channels": {"telegram": {"enabled": True, "token": "tg-tok"}},
            "scheduler": {"enabled": True, "poll_interval": 30},
            "mcp_servers": {},
            "web": {"brave_api_key": "", "fetch_timeout": 20},
            "logging": {"level": "debug"},
        }))
        cfg = load_config(str(cfg_file))
        assert cfg.agent.workspace == "/app/ws"
        assert cfg.provider.api_key == "key123"
        assert cfg.web.brave_api_key is None
        assert cfg.logging.level == "DEBUG"
        assert cfg.scheduler.poll_interval == 30
