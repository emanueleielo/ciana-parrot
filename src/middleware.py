"""Patches for DeepAgents middleware — robust YAML frontmatter parsing + env/bridge filtering."""

import logging
import os
import re

import yaml

import deepagents.middleware.skills as _skills_mod

logger = logging.getLogger(__name__)

_original_parse = _skills_mod._parse_skill_metadata

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Available bridges, set by init_middleware_bridges()
_available_bridges: set[str] = set()


def init_middleware_bridges(gateway_config) -> None:
    """Initialize bridge availability for skill filtering."""
    global _available_bridges
    _available_bridges = set(gateway_config.bridges.keys())
    if _available_bridges:
        logger.info("Middleware bridges available: %s", ", ".join(sorted(_available_bridges)))


def _extract_frontmatter_field(content, field):
    """Extract a single field from raw YAML frontmatter."""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return None
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    if not isinstance(meta, dict):
        return None
    return meta.get(field)


def _extract_requires_env(content):
    """Extract requires_env from raw YAML frontmatter before DeepAgents strips it."""
    return _extract_frontmatter_field(content, "requires_env")


def _check_env_requirements(requires, skill_name):
    """Return False if required environment variables are missing."""
    if not requires:
        return True
    if isinstance(requires, str):
        requires = [requires]
    missing = [var for var in requires if not os.environ.get(var)]
    if missing:
        logger.debug(
            "Skill '%s' skipped — missing env: %s",
            skill_name,
            ", ".join(missing),
        )
        return False
    return True


def _extract_requires_bridge(content):
    """Extract requires_bridge from raw YAML frontmatter."""
    return _extract_frontmatter_field(content, "requires_bridge")


def _check_bridge_requirements(requires, skill_name):
    """Return False if required bridges are not available."""
    if not requires:
        return True
    if isinstance(requires, str):
        requires = [requires]
    missing = [b for b in requires if b not in _available_bridges]
    if missing:
        logger.debug(
            "Skill '%s' skipped — missing bridge: %s",
            skill_name,
            ", ".join(missing),
        )
        return False
    return True


def _robust_parse_skill_metadata(content, skill_path, directory_name):
    """Parse skill metadata with fallback for unquoted YAML values.

    Also filters out skills whose ``requires_env`` vars are not set
    or whose ``requires_bridge`` bridges are not available.
    DeepAgents strips custom frontmatter fields, so we extract
    them ourselves from the raw YAML before delegating.
    """
    # Pre-check: extract requires_env and requires_bridge from raw content
    requires = _extract_requires_env(content)
    if not _check_env_requirements(requires, directory_name):
        return None

    bridge_requires = _extract_requires_bridge(content)
    if not _check_bridge_requirements(bridge_requires, directory_name):
        return None

    result = _original_parse(content, skill_path, directory_name)
    if result is not None:
        return result

    # Original failed — attempt to fix common YAML issues
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return None

    frontmatter_str = match.group(1)
    fixed_lines = []
    changed = False
    for line in frontmatter_str.split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            value_stripped = value.strip()
            if (
                value_stripped
                and not value_stripped.startswith('"')
                and not value_stripped.startswith("'")
                and ": " in value_stripped
            ):
                escaped = value_stripped.replace('"', '\\"')
                fixed_lines.append(f'{key}: "{escaped}"')
                changed = True
                continue
        fixed_lines.append(line)

    if not changed:
        return None

    fixed_frontmatter = "\n".join(fixed_lines)
    fixed_content = content[: match.start(1)] + fixed_frontmatter + content[match.end(1) :]

    logger.info("Retrying skill parse with auto-quoted YAML for %s", skill_path)
    return _original_parse(fixed_content, skill_path, directory_name)


_skills_mod._parse_skill_metadata = _robust_parse_skill_metadata
