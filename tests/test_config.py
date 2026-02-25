"""Tests for src.config — env expansion, validation, load_config."""

import json

import pytest
from pydantic import ValidationError

from src.config import (
    AppConfig,
    AgentConfig,
    BridgeDefinition,
    ChannelsConfig,
    ClaudeCodeConfig,
    GatewayConfig,
    LoggingConfig,
    ModelRouterConfig,
    ProviderConfig,
    SchedulerConfig,
    TelegramChannelConfig,
    TierConfig,
    TranscriptionConfig,
    WebConfig,
    _deep_merge,
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


# --- _deep_merge ---

class TestDeepMerge:
    def test_flat_override(self):
        assert _deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_adds_new_keys(self):
        assert _deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_nested_merge(self):
        base = {"x": {"a": 1, "b": 2}}
        override = {"x": {"b": 3, "c": 4}}
        assert _deep_merge(base, override) == {"x": {"a": 1, "b": 3, "c": 4}}

    def test_override_replaces_non_dict(self):
        assert _deep_merge({"a": {"x": 1}}, {"a": "string"}) == {"a": "string"}

    def test_empty_override(self):
        assert _deep_merge({"a": 1}, {}) == {"a": 1}

    def test_empty_base(self):
        assert _deep_merge({}, {"a": 1}) == {"a": 1}


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


class TestGatewayConfig:
    def test_defaults(self):
        cfg = GatewayConfig()
        assert cfg.enabled is False
        assert cfg.url is None
        assert cfg.port == 9842
        assert cfg.token is None
        assert cfg.default_timeout == 30
        assert cfg.bridges == {}

    def test_url_empty_to_none(self):
        cfg = GatewayConfig(url="")
        assert cfg.url is None

    def test_token_empty_to_none(self):
        cfg = GatewayConfig(token="")
        assert cfg.token is None

    def test_url_value_kept(self):
        cfg = GatewayConfig(url="http://localhost:9842")
        assert cfg.url == "http://localhost:9842"

    def test_token_value_kept(self):
        cfg = GatewayConfig(token="my-secret")
        assert cfg.token == "my-secret"

    def test_bridges_from_dict(self):
        cfg = GatewayConfig(bridges={
            "apple-notes": BridgeDefinition(allowed_commands=["memo"]),
            "spotify": BridgeDefinition(allowed_commands=["spogo"]),
        })
        assert "apple-notes" in cfg.bridges
        assert cfg.bridges["apple-notes"].allowed_commands == ["memo"]
        assert cfg.bridges["spotify"].allowed_commands == ["spogo"]


class TestBridgeDefinition:
    def test_defaults(self):
        bd = BridgeDefinition()
        assert bd.allowed_commands == []

    def test_with_values(self):
        bd = BridgeDefinition(allowed_commands=["memo", "note"])
        assert bd.allowed_commands == ["memo", "note"]


class TestClaudeCodeConfig:
    def test_permission_mode_empty_to_none(self):
        cfg = ClaudeCodeConfig(permission_mode="")
        assert cfg.permission_mode is None

    def test_defaults(self):
        cfg = ClaudeCodeConfig()
        assert cfg.timeout == 0
        assert cfg.claude_path == "claude"
        assert cfg.enabled is False
        assert cfg.projects_dir == "~/.claude/projects"


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


class TestTierConfig:
    def test_required_fields(self):
        cfg = TierConfig(name="anthropic", model="claude-sonnet-4-6")
        assert cfg.name == "anthropic"
        assert cfg.model == "claude-sonnet-4-6"
        assert cfg.api_key is None
        assert cfg.temperature is None
        assert cfg.max_tokens is None
        assert cfg.base_url is None

    def test_temperature_valid(self):
        cfg = TierConfig(name="openai", model="gpt-4", temperature=0.7)
        assert cfg.temperature == 0.7

    def test_temperature_out_of_range(self):
        with pytest.raises(ValidationError, match="temperature"):
            TierConfig(name="openai", model="gpt-4", temperature=3.0)

    def test_temperature_negative(self):
        with pytest.raises(ValidationError, match="temperature"):
            TierConfig(name="openai", model="gpt-4", temperature=-0.1)

    def test_api_key_empty_to_none(self):
        cfg = TierConfig(name="x", model="y", api_key="")
        assert cfg.api_key is None

    def test_api_key_whitespace_to_none(self):
        cfg = TierConfig(name="x", model="y", api_key="  ")
        assert cfg.api_key is None

    def test_api_key_value_kept(self):
        cfg = TierConfig(name="x", model="y", api_key="sk-123")
        assert cfg.api_key == "sk-123"

    def test_base_url_empty_to_none(self):
        cfg = TierConfig(name="x", model="y", base_url="")
        assert cfg.base_url is None

    def test_all_optional_fields(self):
        cfg = TierConfig(
            name="anthropic", model="claude-opus-4-6",
            api_key="key", temperature=1.0, max_tokens=4096,
            base_url="http://localhost:8080",
        )
        assert cfg.max_tokens == 4096
        assert cfg.base_url == "http://localhost:8080"


class TestModelRouterConfig:
    def test_defaults(self):
        cfg = ModelRouterConfig()
        assert cfg.enabled is False
        assert cfg.default_tier == "standard"
        assert cfg.tiers == {}

    def test_enabled_with_tiers(self):
        cfg = ModelRouterConfig(
            enabled=True,
            default_tier="lite",
            tiers={
                "lite": TierConfig(name="google-genai", model="gemini-flash"),
                "standard": TierConfig(name="openai", model="gpt-4o-mini"),
            },
        )
        assert cfg.enabled is True
        assert cfg.default_tier == "lite"
        assert len(cfg.tiers) == 2
        assert cfg.tiers["lite"].name == "google-genai"

    def test_from_dict(self):
        data = {
            "enabled": True,
            "default_tier": "expert",
            "tiers": {
                "expert": {"name": "anthropic", "model": "claude-opus-4-6"},
            },
        }
        cfg = ModelRouterConfig.model_validate(data)
        assert cfg.enabled is True
        assert cfg.default_tier == "expert"
        assert "expert" in cfg.tiers
        assert cfg.tiers["expert"].model == "claude-opus-4-6"

    def test_default_tier_empty_string_invalid(self):
        with pytest.raises(ValidationError, match="default_tier"):
            ModelRouterConfig(default_tier="")

    def test_default_tier_whitespace_invalid(self):
        with pytest.raises(ValidationError, match="default_tier"):
            ModelRouterConfig(default_tier="  ")

    def test_default_tier_not_in_tiers_invalid(self):
        with pytest.raises(ValidationError, match="default_tier.*not defined"):
            ModelRouterConfig(
                enabled=True,
                default_tier="standard",
                tiers={"lite": TierConfig(name="openai", model="gpt-4o-mini")},
            )

    def test_default_tier_not_in_tiers_ok_when_disabled(self):
        """When disabled, default_tier doesn't need to exist in tiers."""
        cfg = ModelRouterConfig(
            enabled=False,
            default_tier="standard",
            tiers={"lite": TierConfig(name="openai", model="gpt-4o-mini")},
        )
        assert cfg.default_tier == "standard"


class TestAppConfig:
    def test_all_defaults(self):
        cfg = AppConfig()
        assert cfg.agent.workspace == "./workspace"
        assert cfg.provider.name == "anthropic"
        assert cfg.channels.telegram.enabled is False
        assert cfg.mcp_servers == {}
        assert cfg.gateway.enabled is False
        assert cfg.gateway.bridges == {}
        assert cfg.model_router.enabled is False
        assert cfg.model_router.tiers == {}

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

    def test_local_override_merges(self, tmp_path):
        """config.local.yaml values override config.yaml."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(json.dumps({
            "agent": {"workspace": "/base"},
            "provider": {"name": "anthropic", "model": "claude-sonnet-4-6"},
        }))
        local_file = tmp_path / "config.local.yaml"
        local_file.write_text(json.dumps({
            "provider": {"model": "gpt-4"},
        }))
        cfg = load_config(str(cfg_file))
        assert cfg.provider.model == "gpt-4"
        assert cfg.provider.name == "anthropic"  # not overridden
        assert cfg.agent.workspace == "/base"     # not overridden

    def test_local_override_adds_new_section(self, tmp_path):
        """config.local.yaml can add sections not in config.yaml."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("agent:\n  workspace: /base\n")
        local_file = tmp_path / "config.local.yaml"
        local_file.write_text(json.dumps({
            "model_router": {
                "enabled": True,
                "default_tier": "lite",
                "tiers": {"lite": {"name": "openai", "model": "gpt-4o-mini"}},
            },
        }))
        cfg = load_config(str(cfg_file))
        assert cfg.model_router.enabled is True
        assert cfg.model_router.default_tier == "lite"
        assert cfg.model_router.tiers["lite"].model == "gpt-4o-mini"

    def test_no_local_override(self, tmp_path):
        """Without config.local.yaml, load_config works as before."""
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("agent:\n  workspace: /base\n")
        cfg = load_config(str(cfg_file))
        assert cfg.agent.workspace == "/base"

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
