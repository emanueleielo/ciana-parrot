"""Tests for middleware requires_bridge filtering."""

import pytest

from src.middleware import (
    _check_bridge_requirements,
    _extract_requires_bridge,
    init_middleware_bridges,
)


@pytest.fixture(autouse=True)
def reset_bridges():
    """Reset available bridges before each test."""
    import src.middleware as mod
    old = mod._available_bridges
    yield
    mod._available_bridges = old


class TestExtractRequiresBridge:
    def test_single_bridge(self):
        content = "---\nname: test\nrequires_bridge:\n  - apple-notes\n---\nBody"
        result = _extract_requires_bridge(content)
        assert result == ["apple-notes"]

    def test_multiple_bridges(self):
        content = "---\nname: test\nrequires_bridge:\n  - apple-notes\n  - spotify\n---\nBody"
        result = _extract_requires_bridge(content)
        assert result == ["apple-notes", "spotify"]

    def test_no_requires_bridge(self):
        content = "---\nname: test\n---\nBody"
        result = _extract_requires_bridge(content)
        assert result is None

    def test_no_frontmatter(self):
        content = "Just a plain SKILL.md with no YAML."
        result = _extract_requires_bridge(content)
        assert result is None

    def test_string_value(self):
        content = '---\nname: test\nrequires_bridge: "apple-notes"\n---\nBody'
        result = _extract_requires_bridge(content)
        assert result == "apple-notes"


class TestCheckBridgeRequirements:
    def test_bridge_available(self):
        import src.middleware as mod
        mod._available_bridges = {"apple-notes", "spotify"}
        assert _check_bridge_requirements(["apple-notes"], "test-skill")

    def test_bridge_missing(self):
        import src.middleware as mod
        mod._available_bridges = {"spotify"}
        assert not _check_bridge_requirements(["apple-notes"], "test-skill")

    def test_no_requirements(self):
        assert _check_bridge_requirements(None, "test-skill")

    def test_empty_list(self):
        assert _check_bridge_requirements([], "test-skill")

    def test_multiple_all_present(self):
        import src.middleware as mod
        mod._available_bridges = {"apple-notes", "spotify", "apple-reminders"}
        assert _check_bridge_requirements(
            ["apple-notes", "spotify"], "test-skill"
        )

    def test_multiple_one_missing(self):
        import src.middleware as mod
        mod._available_bridges = {"apple-notes"}
        assert not _check_bridge_requirements(
            ["apple-notes", "spotify"], "test-skill"
        )

    def test_string_value(self):
        import src.middleware as mod
        mod._available_bridges = {"apple-notes"}
        assert _check_bridge_requirements("apple-notes", "test-skill")

    def test_string_value_missing(self):
        import src.middleware as mod
        mod._available_bridges = set()
        assert not _check_bridge_requirements("apple-notes", "test-skill")


class TestInitMiddlewareBridges:
    def test_sets_bridges(self):
        from src.config import BridgeDefinition, GatewayConfig
        config = GatewayConfig(
            enabled=True,
            bridges={
                "apple-notes": BridgeDefinition(allowed_commands=["memo"]),
                "spotify": BridgeDefinition(allowed_commands=["spogo"]),
            },
        )
        init_middleware_bridges(config)
        import src.middleware as mod
        assert mod._available_bridges == {"apple-notes", "spotify"}

    def test_empty_bridges(self):
        from src.config import GatewayConfig
        config = GatewayConfig(enabled=True)
        init_middleware_bridges(config)
        import src.middleware as mod
        assert mod._available_bridges == set()
