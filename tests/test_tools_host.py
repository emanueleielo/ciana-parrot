"""Tests for src.tools.host — host_execute tool."""

from unittest.mock import AsyncMock

import pytest

from src.config import BridgeDefinition, GatewayConfig
from src.gateway.client import GatewayResult
from src.tools.host import host_execute, init_host_tools, _gateway_client


@pytest.fixture(autouse=True)
def reset_module_state():
    """Reset module-level state before each test."""
    import src.tools.host as mod
    old_client = mod._gateway_client
    old_bridges = mod._available_bridges
    old_timeout = mod._default_timeout
    yield
    mod._gateway_client = old_client
    mod._available_bridges = old_bridges
    mod._default_timeout = old_timeout


@pytest.fixture
def gateway_config():
    return GatewayConfig(
        enabled=True,
        url="http://localhost:9842",
        token="test",
        default_timeout=30,
        bridges={
            "apple-notes": BridgeDefinition(allowed_commands=["memo"]),
            "spotify": BridgeDefinition(allowed_commands=["spogo"]),
        },
    )


class TestInitHostTools:
    def test_sets_client_and_bridges(self, gateway_config):
        init_host_tools(gateway_config)
        import src.tools.host as mod
        assert mod._gateway_client is not None
        assert "apple-notes" in mod._available_bridges
        assert "spotify" in mod._available_bridges

    def test_no_url_no_client(self):
        config = GatewayConfig(enabled=True, url=None)
        init_host_tools(config)
        import src.tools.host as mod
        assert mod._gateway_client is None


class TestHostExecute:
    @pytest.mark.asyncio
    async def test_gateway_not_configured(self):
        import src.tools.host as mod
        mod._gateway_client = None
        mod._available_bridges = {}
        result = await host_execute.ainvoke({"bridge": "test", "command": "ls"})
        assert "not configured" in result

    @pytest.mark.asyncio
    async def test_unknown_bridge(self, gateway_config):
        init_host_tools(gateway_config)
        result = await host_execute.ainvoke({"bridge": "unknown", "command": "ls"})
        assert "unknown bridge" in result.lower()
        assert "apple-notes" in result  # Should list available bridges

    @pytest.mark.asyncio
    async def test_execution_success(self, gateway_config):
        init_host_tools(gateway_config)
        import src.tools.host as mod
        mock_result = GatewayResult(stdout="Note 1\nNote 2\n", returncode=0)
        mock_client = AsyncMock()
        mock_client.execute = AsyncMock(return_value=mock_result)
        mod._gateway_client = mock_client

        result = await host_execute.ainvoke({
            "bridge": "apple-notes",
            "command": "memo list",
        })
        assert "Note 1" in result
        assert "Note 2" in result

        # Verify shlex split
        mock_client.execute.assert_called_once()
        call_kwargs = mock_client.execute.call_args
        assert call_kwargs.kwargs["cmd"] == ["memo", "list"]
        assert call_kwargs.kwargs["bridge"] == "apple-notes"

    @pytest.mark.asyncio
    async def test_nonzero_exit_code(self, gateway_config):
        init_host_tools(gateway_config)
        import src.tools.host as mod
        mod._gateway_client = AsyncMock()
        mod._gateway_client.execute = AsyncMock(
            return_value=GatewayResult(stdout="", stderr="not found", returncode=1)
        )
        result = await host_execute.ainvoke({
            "bridge": "apple-notes",
            "command": "memo get nonexistent",
        })
        assert "failed" in result.lower()
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_stderr_in_output(self, gateway_config):
        init_host_tools(gateway_config)
        import src.tools.host as mod
        mod._gateway_client = AsyncMock()
        mod._gateway_client.execute = AsyncMock(
            return_value=GatewayResult(stdout="", stderr="warning msg", returncode=1)
        )
        result = await host_execute.ainvoke({
            "bridge": "apple-notes",
            "command": "memo list",
        })
        assert "warning msg" in result

    @pytest.mark.asyncio
    async def test_output_truncation(self, gateway_config):
        init_host_tools(gateway_config)
        import src.tools.host as mod
        mod._gateway_client = AsyncMock()
        long_output = "x" * 20_000
        mod._gateway_client.execute = AsyncMock(
            return_value=GatewayResult(stdout=long_output, returncode=0)
        )
        result = await host_execute.ainvoke({
            "bridge": "apple-notes",
            "command": "memo list",
        })
        assert len(result) < 20_000
        assert "truncated" in result

    @pytest.mark.asyncio
    async def test_shlex_split_quoted(self, gateway_config):
        init_host_tools(gateway_config)
        import src.tools.host as mod
        mod._gateway_client = AsyncMock()
        mod._gateway_client.execute = AsyncMock(
            return_value=GatewayResult(stdout="ok", returncode=0)
        )
        await host_execute.ainvoke({
            "bridge": "spotify",
            "command": "spogo play 'My Song Name'",
        })
        call_kwargs = mod._gateway_client.execute.call_args
        assert call_kwargs.kwargs["cmd"] == ["spogo", "play", "My Song Name"]

    @pytest.mark.asyncio
    async def test_gateway_error(self, gateway_config):
        init_host_tools(gateway_config)
        import src.tools.host as mod
        mod._gateway_client = AsyncMock()
        mod._gateway_client.execute = AsyncMock(
            return_value=GatewayResult(error="Connection refused")
        )
        result = await host_execute.ainvoke({
            "bridge": "apple-notes",
            "command": "memo list",
        })
        assert "Connection refused" in result

    @pytest.mark.asyncio
    async def test_empty_output(self, gateway_config):
        init_host_tools(gateway_config)
        import src.tools.host as mod
        mod._gateway_client = AsyncMock()
        mod._gateway_client.execute = AsyncMock(
            return_value=GatewayResult(stdout="", returncode=0)
        )
        result = await host_execute.ainvoke({
            "bridge": "apple-notes",
            "command": "memo list",
        })
        assert "no output" in result.lower()

    @pytest.mark.asyncio
    async def test_default_timeout_used(self, gateway_config):
        init_host_tools(gateway_config)
        import src.tools.host as mod
        mod._gateway_client = AsyncMock()
        mod._gateway_client.execute = AsyncMock(
            return_value=GatewayResult(stdout="ok", returncode=0)
        )
        await host_execute.ainvoke({
            "bridge": "apple-notes",
            "command": "memo list",
        })
        call_kwargs = mod._gateway_client.execute.call_args
        assert call_kwargs.kwargs["timeout"] == 30  # default_timeout from config
