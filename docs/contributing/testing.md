---
title: Testing
---

# Testing

CianaParrot has a comprehensive test suite covering configuration validation, message routing, scheduling, Telegram formatting, bridge NDJSON parsing, gateway validation, tool behavior, and middleware filtering.

---

## Running Tests

The quickest way to run the full suite:

```bash
make test
```

This executes:

```bash
python3 -m pytest tests/ -v
```

!!! tip "Running a specific test file"
    ```bash
    python3 -m pytest tests/test_router.py -v
    ```

!!! tip "Running a specific test function"
    ```bash
    python3 -m pytest tests/test_router.py::test_group_message_without_trigger -v
    ```

---

## Test Suite Overview

The test suite currently contains **506 tests** across the following areas:

| Area | Test File(s) | What It Covers |
|------|-------------|----------------|
| **Config validation** | `tests/test_config.py` | Pydantic model validation, env var expansion, defaults, error cases |
| **Message routing** | `tests/test_router.py` | User allowlists, trigger detection, thread ID generation, session resets |
| **Scheduling** | `tests/test_scheduler.py` | Cron expressions, intervals, one-shot tasks, task activation/deactivation |
| **Telegram formatting** | `tests/test_formatting.py` | Markdown-to-HTML conversion, code block protection, message chunking |
| **Bridge parsing** | `tests/test_bridge.py` | NDJSON streaming output parsing, CCResponse event construction |
| **Gateway validation** | `tests/test_gateway.py` | Command allowlist enforcement, request validation, error handling |
| **Tool behavior** | `tests/test_tools.py` | Web search/fetch tools, cron tools, host_execute tool |
| **Middleware** | `tests/test_middleware.py` | Skill filtering by bridge availability |

---

## Test Structure

Tests mirror the source directory structure:

```
tests/
  test_config.py        # src/config.py
  test_router.py        # src/router.py
  test_scheduler.py     # src/scheduler.py
  test_formatting.py    # src/channels/telegram/formatting.py
  test_bridge.py        # src/gateway/bridges/claude_code/bridge.py
  test_gateway.py       # src/gateway/server.py
  test_tools.py         # src/tools/*.py
  test_middleware.py     # src/middleware.py
```

When adding a new module, create a corresponding test file following this pattern.

---

## Writing Tests

### General Guidelines

1. **Every new feature or bug fix should include tests.** If you are adding a new tool, channel, bridge, or config section, write tests that verify the expected behavior.

2. **Tests should be fast.** No real API calls, no network requests, no Docker dependencies. Mock external services.

3. **Use pytest fixtures** for common setup (config objects, mock channels, mock routers).

4. **Keep tests focused.** Each test function should verify one behavior. Prefer many small tests over few large ones.

### Example: Testing a New Tool

```python title="tests/test_my_tool.py"
import pytest
from unittest.mock import AsyncMock, patch


@pytest.fixture
def mock_config():
    """Provide a minimal config for the tool under test."""
    return {"api_key": "test-key", "timeout": 30}


def test_tool_validates_input():
    """Verify the tool rejects invalid input."""
    from src.tools.my_tool import my_tool_func

    with pytest.raises(ValueError, match="input cannot be empty"):
        my_tool_func.invoke({"query": ""})


@pytest.mark.asyncio
async def test_tool_calls_external_api(mock_config):
    """Verify the tool calls the external API with correct parameters."""
    with patch("src.tools.my_tool.external_client") as mock_client:
        mock_client.search = AsyncMock(return_value={"results": []})

        from src.tools.my_tool import my_tool_func
        result = await my_tool_func.ainvoke({"query": "test"})

        mock_client.search.assert_called_once_with("test")
        assert "results" in result
```

### Example: Testing Config Validation

```python title="tests/test_config.py (excerpt)"
import pytest
from pydantic import ValidationError
from src.config import AppConfig


def test_missing_required_field():
    """Config should fail validation when a required field is missing."""
    with pytest.raises(ValidationError):
        AppConfig(**{"provider": {}})  # missing required fields


def test_default_values():
    """Config should apply sensible defaults."""
    config = AppConfig(**minimal_valid_config)
    assert config.scheduler.enabled is True
    assert config.web.search_provider == "brave"
```

---

## Mocking Patterns

!!! info "No real API calls"
    All tests must run without network access. Use `unittest.mock.patch` and `AsyncMock` to replace external dependencies.

### Common mocking targets

| What to Mock | How |
|-------------|-----|
| HTTP requests | `patch("httpx.AsyncClient.get")` or `patch("aiohttp.ClientSession.get")` |
| LLM calls | `patch("langchain.chat_models.init_chat_model")` returning a mock with `.ainvoke()` |
| Telegram API | `patch("telegram.Bot.send_message")` with `AsyncMock` |
| File I/O | `tmp_path` fixture or `patch("builtins.open")` |
| Gateway client | `patch("src.gateway.client.GatewayClient.execute")` with `AsyncMock` |

---

## Running Tests in Docker

If you prefer to run tests inside the container:

```bash
make shell
# Inside the container:
python -m pytest tests/ -v
```

---

## Continuous Integration

!!! note "Pre-commit hooks"
    The repository includes a gitleaks pre-commit hook for secret scanning. This runs automatically before each commit. See [Git Guidelines](git-guidelines.md) for details.

When submitting a pull request, ensure all tests pass locally before pushing. The test suite should complete in under 30 seconds.

---

## Next Steps

- Review the coding standards: [Code Conventions](code-conventions.md)
- Understand the git workflow: [Git Guidelines](git-guidelines.md)
