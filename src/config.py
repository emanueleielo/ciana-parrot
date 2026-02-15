"""Configuration loader - parses config.yaml with env var expansion."""

import os
import re
from pathlib import Path
from typing import Any

import yaml

_ENV_RE = re.compile(r"\$\{([^}]+)\}")


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


def load_config(path: str = "config.yaml") -> dict:
    """Load and validate config from YAML file."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    config = _walk_expand(raw)

    # Defaults
    config.setdefault("agent", {})
    config["agent"].setdefault("workspace", "./workspace")
    config["agent"].setdefault("max_tool_iterations", 20)
    config.setdefault("provider", {})
    config.setdefault("channels", {})
    config.setdefault("scheduler", {"enabled": False})
    config.setdefault("mcp_servers", {})
    config.setdefault("skills", {"directory": "./skills", "enabled": True})
    config.setdefault("web", {})
    config.setdefault("logging", {"level": "INFO"})

    return config
