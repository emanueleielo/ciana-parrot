"""Configuration loader - parses config.yaml with env var expansion and Pydantic validation."""

import os
import re
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

_ENV_RE = re.compile(r"\$\{([^}]+)\}")

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _expand_env(value: str) -> str:
    """Replace ${VAR} patterns with environment variable values."""
    def _replace(match: re.Match) -> str:
        var = match.group(1)
        return os.environ.get(var, "")
    return _ENV_RE.sub(_replace, value)


def _walk_expand(obj: Any) -> Any:
    """Recursively expand env vars in strings throughout a dict/list."""
    if isinstance(obj, str):
        return _expand_env(obj)
    if isinstance(obj, dict):
        return {k: _walk_expand(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_expand(i) for i in obj]
    return obj


# --- Pydantic models ---


def _empty_str_to_none(v: Any) -> Optional[str]:
    """Convert empty strings to None for optional string fields."""
    if isinstance(v, str) and not v.strip():
        return None
    return v


class TierConfig(BaseModel):
    """Configuration for a single model tier."""
    name: str                          # Provider name (anthropic, openai, etc.)
    model: str                         # Model identifier
    api_key: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    base_url: Optional[str] = None

    @field_validator("api_key", "base_url", mode="before")
    @classmethod
    def _empty_to_none(cls, v: Any) -> Optional[str]:
        return _empty_str_to_none(v)

    @field_validator("temperature")
    @classmethod
    def _check_temperature(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 2.0):
            raise ValueError("temperature must be between 0.0 and 2.0")
        return v


class ModelRouterConfig(BaseModel):
    """Multi-tier model routing configuration."""
    enabled: bool = False
    default_tier: str = "standard"
    tiers: dict[str, TierConfig] = Field(default_factory=dict)

    @field_validator("default_tier")
    @classmethod
    def _check_default_tier(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("default_tier must not be empty")
        return v

    @model_validator(mode="after")
    def _check_default_tier_in_tiers(self) -> "ModelRouterConfig":
        if self.enabled and self.tiers and self.default_tier not in self.tiers:
            raise ValueError(
                f"default_tier '{self.default_tier}' is not defined in tiers: "
                f"{sorted(self.tiers.keys())}"
            )
        return self


class AgentConfig(BaseModel):
    workspace: str = "./workspace"
    data_dir: str = "./data"
    max_tool_iterations: int = 20


class ProviderConfig(BaseModel):
    name: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    api_key: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    base_url: Optional[str] = None

    @field_validator("api_key", "base_url", mode="before")
    @classmethod
    def _empty_to_none(cls, v: Any) -> Optional[str]:
        return _empty_str_to_none(v)

    @field_validator("temperature")
    @classmethod
    def _check_temperature(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 2.0):
            raise ValueError("temperature must be between 0.0 and 2.0")
        return v


class TelegramChannelConfig(BaseModel):
    enabled: bool = False
    token: str = ""
    trigger: str = "@Ciana"
    allowed_users: list[str] = Field(default_factory=list)

    @field_validator("allowed_users", mode="before")
    @classmethod
    def _coerce_to_str(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(item) for item in v]
        return v


class ChannelsConfig(BaseModel):
    telegram: TelegramChannelConfig = Field(default_factory=TelegramChannelConfig)


class SchedulerConfig(BaseModel):
    enabled: bool = False
    poll_interval: int = 60
    data_file: str = "./data/scheduled_tasks.json"

    @field_validator("poll_interval")
    @classmethod
    def _check_poll_interval(cls, v: int) -> int:
        if v < 1:
            raise ValueError("poll_interval must be >= 1")
        return v


class SkillsConfig(BaseModel):
    enabled: bool = True
    directory: str = "skills"  # Virtual path relative to workspace


class WebConfig(BaseModel):
    brave_api_key: Optional[str] = None
    fetch_timeout: int = 30

    @field_validator("brave_api_key", mode="before")
    @classmethod
    def _empty_to_none(cls, v: Any) -> Optional[str]:
        return _empty_str_to_none(v)


class TranscriptionConfig(BaseModel):
    enabled: bool = False
    provider: str = "groq"        # "groq" | "openai"
    model: str = "whisper-large-v3-turbo"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: int = 30

    @field_validator("api_key", "base_url", mode="before")
    @classmethod
    def _empty_to_none(cls, v: Any) -> Optional[str]:
        return _empty_str_to_none(v)

    @field_validator("provider")
    @classmethod
    def _check_provider(cls, v: str) -> str:
        if v not in ("groq", "openai"):
            raise ValueError("transcription provider must be 'groq' or 'openai'")
        return v


class BridgeDefinition(BaseModel):
    allowed_commands: list[str] = Field(default_factory=list)
    allowed_cwd: list[str] = Field(default_factory=list)


class GatewayConfig(BaseModel):
    enabled: bool = False
    url: Optional[str] = None
    token: Optional[str] = None
    port: int = 9842
    default_timeout: int = 30
    bridges: dict[str, BridgeDefinition] = Field(default_factory=dict)

    @field_validator("url", "token", mode="before")
    @classmethod
    def _empty_to_none(cls, v: Any) -> Optional[str]:
        return _empty_str_to_none(v)


class ClaudeCodeConfig(BaseModel):
    enabled: bool = False
    bridge_url: Optional[str] = None
    bridge_token: Optional[str] = None
    projects_dir: str = "~/.claude/projects"
    permission_mode: Optional[str] = None
    timeout: int = 0
    claude_path: str = "claude"
    state_file: str = "data/cc_user_states.json"

    @field_validator("bridge_url", "bridge_token", "permission_mode", mode="before")
    @classmethod
    def _empty_to_none(cls, v: Any) -> Optional[str]:
        return _empty_str_to_none(v)


class LoggingConfig(BaseModel):
    level: str = "INFO"

    @field_validator("level")
    @classmethod
    def _check_level(cls, v: str) -> str:
        v = v.upper()
        if v not in _VALID_LOG_LEVELS:
            raise ValueError(f"logging level must be one of {_VALID_LOG_LEVELS}")
        return v


class AppConfig(BaseModel):
    agent: AgentConfig = Field(default_factory=AgentConfig)
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    mcp_servers: dict[str, dict[str, Any]] = Field(default_factory=dict)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    model_router: ModelRouterConfig = Field(default_factory=ModelRouterConfig)
    claude_code: ClaudeCodeConfig = Field(default_factory=ClaudeCodeConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override values win."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: str = "config.yaml") -> AppConfig:
    """Load and validate config from YAML file.

    If a config.local.yaml exists alongside the main config, it is
    deep-merged on top (local overrides win). This allows local-only
    configuration without modifying the committed config.yaml.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    # Merge local override if present
    local_path = config_path.with_name("config.local.yaml")
    if local_path.exists():
        with open(local_path) as f:
            local_raw = yaml.safe_load(f) or {}
        raw = _deep_merge(raw, local_raw)

    expanded = _walk_expand(raw)
    return AppConfig.model_validate(expanded)
