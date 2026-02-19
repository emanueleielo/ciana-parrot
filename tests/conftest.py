"""Shared test fixtures."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import (
    AgentConfig,
    AppConfig,
    ChannelsConfig,
    ClaudeCodeConfig,
    LoggingConfig,
    ProviderConfig,
    SchedulerConfig,
    SkillsConfig,
    TelegramChannelConfig,
    WebConfig,
)


@pytest.fixture
def app_config(tmp_path) -> AppConfig:
    """Full config with temp workspace."""
    return AppConfig(
        agent=AgentConfig(workspace=str(tmp_path / "workspace")),
        provider=ProviderConfig(name="anthropic", model="test"),
        channels=ChannelsConfig(
            telegram=TelegramChannelConfig(
                enabled=True,
                token="test-token",
                trigger="@TestBot",
                allowed_users=["user1", "user2"],
            )
        ),
        scheduler=SchedulerConfig(
            data_file=str(tmp_path / "tasks.json"),
        ),
        mcp_servers={},
        skills=SkillsConfig(),
        web=WebConfig(brave_api_key="test-key", fetch_timeout=10),
        claude_code=ClaudeCodeConfig(
            enabled=True,
            state_file=str(tmp_path / "cc_states.json"),
            projects_dir=str(tmp_path / "projects"),
        ),
        logging=LoggingConfig(),
    )


@pytest.fixture
def mock_agent() -> AsyncMock:
    """Mock agent.ainvoke() returning simple text response."""
    agent = AsyncMock()
    mock_msg = MagicMock(content="Test response", tool_calls=[])
    agent.ainvoke.return_value = {"messages": [mock_msg]}
    return agent


@pytest.fixture(autouse=True)
def reset_tool_globals():
    """Save/restore module-level globals between tests."""
    from src.tools import web, cron

    old_brave = web._brave_api_key
    old_timeout = web._fetch_timeout
    old_data_file = cron._data_file
    yield
    web._brave_api_key = old_brave
    web._fetch_timeout = old_timeout
    cron._data_file = old_data_file


@pytest.fixture
def json_file(tmp_path):
    """Factory for temp JSON files."""
    def _create(data, filename="test.json") -> Path:
        p = tmp_path / filename
        p.write_text(json.dumps(data))
        return p
    return _create
