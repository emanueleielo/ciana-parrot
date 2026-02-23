"""Tests for middleware — env filtering, YAML parsing, robust parse."""

import pytest
from unittest.mock import patch, MagicMock

from src.middleware import (
    _extract_frontmatter_field,
    _extract_requires_env,
    _check_env_requirements,
    _robust_parse_skill_metadata,
    _original_parse,
)
import src.middleware as middleware_mod


class TestExtractFrontmatterField:
    def test_valid_yaml_returns_field(self):
        content = "---\nname: test\n---\nBody content here."
        result = _extract_frontmatter_field(content, "name")
        assert result == "test"

    def test_invalid_yaml_returns_none(self):
        content = "---\n{invalid: [yaml\n---\nBody"
        result = _extract_frontmatter_field(content, "invalid")
        assert result is None

    def test_no_frontmatter_returns_none(self):
        content = "No YAML here, just plain text."
        result = _extract_frontmatter_field(content, "name")
        assert result is None

    def test_non_dict_returns_none(self):
        """YAML that parses to a list instead of a dict should return None."""
        content = "---\n- item1\n- item2\n---\nBody"
        result = _extract_frontmatter_field(content, "name")
        assert result is None


class TestExtractRequiresEnv:
    def test_extracts_list(self):
        content = '---\nrequires_env: ["KEY1", "KEY2"]\n---\nBody'
        result = _extract_requires_env(content)
        assert result == ["KEY1", "KEY2"]

    def test_extracts_string(self):
        content = '---\nrequires_env: "SINGLE_KEY"\n---\nBody'
        result = _extract_requires_env(content)
        assert result == "SINGLE_KEY"


class TestCheckEnvRequirements:
    def test_env_present(self, monkeypatch):
        monkeypatch.setenv("MY_KEY", "val")
        assert _check_env_requirements(["MY_KEY"], "skill") is True

    def test_env_missing(self, monkeypatch):
        monkeypatch.delenv("MY_KEY", raising=False)
        assert _check_env_requirements(["MY_KEY"], "skill") is False

    def test_string_value_wraps_to_list(self, monkeypatch):
        """A single string requirement should be treated like a one-element list."""
        monkeypatch.setenv("SOLO_VAR", "present")
        assert _check_env_requirements("SOLO_VAR", "skill") is True

        monkeypatch.delenv("SOLO_VAR", raising=False)
        assert _check_env_requirements("SOLO_VAR", "skill") is False


class TestRobustParseSkillMetadata:
    def test_delegates_to_original(self, monkeypatch):
        """When env is satisfied, it should call _original_parse and return its result."""
        sentinel = MagicMock(name="parsed_result")
        monkeypatch.setattr(middleware_mod, "_original_parse", lambda c, p, n: sentinel)
        content = "---\nname: test\n---\nBody"
        result = _robust_parse_skill_metadata(content, "/path/skill", "my-skill")
        assert result is sentinel

    def test_env_missing_returns_none(self, monkeypatch):
        """If requires_env var is missing, return None without calling _original_parse."""
        monkeypatch.delenv("MISSING_VAR", raising=False)
        calls = []
        monkeypatch.setattr(
            middleware_mod, "_original_parse",
            lambda c, p, n: calls.append(1) or MagicMock(),
        )
        content = '---\nname: test\nrequires_env: ["MISSING_VAR"]\n---\nBody'
        result = _robust_parse_skill_metadata(content, "/path/skill", "my-skill")
        assert result is None
        assert len(calls) == 0, "_original_parse should not have been called"

    def test_auto_quote_fix(self, monkeypatch):
        """When original parse fails on unquoted YAML value with colon, retry with auto-quoting."""
        call_count = {"n": 0}
        sentinel = MagicMock(name="fixed_result")

        def fake_original(content, path, name):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return None  # first call fails
            return sentinel  # second call succeeds after fix

        monkeypatch.setattr(middleware_mod, "_original_parse", fake_original)
        content = "---\nname: test\ndescription: Value: with colon inside\n---\nBody"
        result = _robust_parse_skill_metadata(content, "/path/skill", "my-skill")
        assert result is sentinel
        assert call_count["n"] == 2

    def test_no_frontmatter_returns_none(self, monkeypatch):
        """Content without frontmatter: _original_parse returns None, robust returns None."""
        monkeypatch.setattr(middleware_mod, "_original_parse", lambda c, p, n: None)
        content = "No YAML frontmatter at all."
        result = _robust_parse_skill_metadata(content, "/path/skill", "my-skill")
        assert result is None


class TestMonkeyPatch:
    def test_parse_is_patched(self):
        """The middleware module should have patched _parse_skill_metadata on import."""
        assert middleware_mod._skills_mod._parse_skill_metadata is _robust_parse_skill_metadata
