"""Tests for setup_bridge — Claude Code bridge initialization."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bridges.claude_code import setup_bridge
from src.config import AppConfig, ClaudeCodeConfig, GatewayConfig


class TestSetupBridge:
    @pytest.mark.asyncio
    async def test_disabled_returns_early(self, tmp_path):
        config = AppConfig(
            claude_code=ClaudeCodeConfig(
                enabled=False,
                state_file=str(tmp_path / "s.json"),
                projects_dir=str(tmp_path / "p"),
            ),
        )
        mock_channel = MagicMock()
        await setup_bridge(config, mock_channel)
        mock_channel.register_mode_handler.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.bridges.claude_code.ClaudeCodeBridge")
    @patch("src.bridges.claude_code.GatewayClient")
    async def test_gateway_enabled_creates_client(self, MockGateway, MockBridge, tmp_path):
        mock_bridge_instance = MagicMock()
        mock_bridge_instance.check_available = AsyncMock(return_value=(True, "ok"))
        MockBridge.return_value = mock_bridge_instance

        config = AppConfig(
            claude_code=ClaudeCodeConfig(
                enabled=True,
                state_file=str(tmp_path / "s.json"),
                projects_dir=str(tmp_path / "p"),
            ),
            gateway=GatewayConfig(
                enabled=True,
                url="http://localhost:9842",
                token="tok",
            ),
        )
        mock_channel = MagicMock()
        await setup_bridge(config, mock_channel)
        MockGateway.assert_called_once_with("http://localhost:9842", "tok")
        mock_channel.register_mode_handler.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.bridges.claude_code.ClaudeCodeBridge")
    async def test_bridge_available_logs_ready(self, MockBridge, tmp_path):
        mock_bridge_instance = MagicMock()
        mock_bridge_instance.check_available = AsyncMock(return_value=(True, "v1.0"))
        MockBridge.return_value = mock_bridge_instance

        config = AppConfig(
            claude_code=ClaudeCodeConfig(
                enabled=True,
                state_file=str(tmp_path / "s.json"),
                projects_dir=str(tmp_path / "p"),
            ),
        )
        mock_channel = MagicMock()
        await setup_bridge(config, mock_channel)
        mock_bridge_instance.check_available.assert_awaited_once()
        mock_channel.register_mode_handler.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.bridges.claude_code.ClaudeCodeBridge")
    async def test_bridge_not_available_still_registers(self, MockBridge, tmp_path):
        mock_bridge_instance = MagicMock()
        mock_bridge_instance.check_available = AsyncMock(return_value=(False, "not found"))
        MockBridge.return_value = mock_bridge_instance

        config = AppConfig(
            claude_code=ClaudeCodeConfig(
                enabled=True,
                state_file=str(tmp_path / "s.json"),
                projects_dir=str(tmp_path / "p"),
            ),
        )
        mock_channel = MagicMock()
        await setup_bridge(config, mock_channel)
        mock_bridge_instance.check_available.assert_awaited_once()
        # Handler is still registered even when bridge is unavailable
        mock_channel.register_mode_handler.assert_called_once()
