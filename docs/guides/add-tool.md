---
title: Add a Tool
---

# Add a Tool

This guide walks you through creating a new agent tool using the module-level init pattern that all CianaParrot tools follow.

---

## Introduction

Tools are `@tool`-decorated functions that the agent can call during conversations. Unlike skills (which are auto-discovered from the `workspace/skills/` directory), tools live in `src/tools/` and are manually wired into the agent. Tools are the right choice when you need:

- Access to application config at module level
- Integration with external services requiring initialization
- Tight coupling with core infrastructure (gateway client, scheduler, etc.)

All tools in CianaParrot follow the same pattern: a module-level `init_*()` function sets globals from config, and `@tool` functions read those globals at call time.

---

## Prerequisites

- A working CianaParrot installation ([Installation Guide](../getting-started/installation.md))
- Python 3.13+
- Familiarity with `langchain_core.tools.tool` decorator

---

## Step 1: Review the Existing Pattern

Here is a simplified view of the pattern used by `src/tools/web.py`:

```python title="src/tools/web.py (simplified reference)"
from typing import Optional
from langchain_core.tools import tool
from ..config import WebConfig

# Module-level config, set by init_web_tools()
_brave_api_key: Optional[str] = None
_fetch_timeout: int = 30


def init_web_tools(config: WebConfig) -> None:
    """Initialize web tools with config values."""
    global _brave_api_key, _fetch_timeout
    _brave_api_key = config.brave_api_key
    _fetch_timeout = config.fetch_timeout


@tool
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for information."""
    # Uses _brave_api_key set during init
    ...
```

The three existing tool modules:

| Module | Init function | Tools |
|--------|--------------|-------|
| `src/tools/web.py` | `init_web_tools(WebConfig)` | `web_search`, `web_fetch` |
| `src/tools/cron.py` | `init_cron_tools(SchedulerConfig)` | `schedule_task`, `list_tasks`, `cancel_task` |
| `src/tools/host.py` | `init_host_tools(GatewayConfig)` | `host_execute` |

---

## Step 2: Create the Tool Module

Create a new file in `src/tools/`:

```python title="src/tools/weather.py"
"""Weather tools — fetch current weather and forecasts."""

import logging
from typing import Optional

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Module-level config, set by init_weather_tools()
_api_key: Optional[str] = None
_timeout: int = 15


def init_weather_tools(api_key: Optional[str], timeout: int = 15) -> None:
    """Initialize weather tools with config values."""
    global _api_key, _timeout
    _api_key = api_key
    _timeout = timeout


@tool
async def get_weather(location: str) -> str:
    """Get the current weather for a location.

    Args:
        location: City name or coordinates (e.g. "London" or "51.5,-0.1").
    """
    if not _api_key:
        return "Weather API key not configured."

    try:
        async with httpx.AsyncClient(timeout=_timeout) as client:
            resp = await client.get(
                "https://api.weatherapi.com/v1/current.json",
                params={"key": _api_key, "q": location},
            )
        resp.raise_for_status()
        data = resp.json()
        current = data["current"]
        loc = data["location"]
        return (
            f"Weather in {loc['name']}, {loc['country']}:\n"
            f"  Temperature: {current['temp_c']}C / {current['temp_f']}F\n"
            f"  Condition: {current['condition']['text']}\n"
            f"  Humidity: {current['humidity']}%\n"
            f"  Wind: {current['wind_kph']} km/h {current['wind_dir']}"
        )
    except httpx.HTTPStatusError as e:
        return f"Weather API error: {e.response.status_code}"
    except Exception as e:
        logger.exception("Weather fetch failed for %s", location)
        return f"Error fetching weather: {e}"


@tool
async def get_forecast(location: str, days: int = 3) -> str:
    """Get a weather forecast for a location.

    Args:
        location: City name or coordinates.
        days: Number of forecast days (1-7).
    """
    if not _api_key:
        return "Weather API key not configured."

    days = max(1, min(7, days))

    try:
        async with httpx.AsyncClient(timeout=_timeout) as client:
            resp = await client.get(
                "https://api.weatherapi.com/v1/forecast.json",
                params={"key": _api_key, "q": location, "days": days},
            )
        resp.raise_for_status()
        data = resp.json()
        lines = [f"Forecast for {data['location']['name']}:"]
        for day in data["forecast"]["forecastday"]:
            d = day["day"]
            lines.append(
                f"  {day['date']}: {d['condition']['text']}, "
                f"{d['mintemp_c']}-{d['maxtemp_c']}C"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.exception("Forecast fetch failed for %s", location)
        return f"Error fetching forecast: {e}"
```

!!! tip "Async by default"
    All tool functions should be `async def` since the agent invokes them in an async context. Use `httpx.AsyncClient` instead of `requests` for HTTP calls.

---

## Step 3: Add Config Support (if needed)

If your tool needs config values beyond what already exists, add a config section. See [Add a Config Section](add-config-section.md) for the full pattern. Quick version:

```python title="src/config.py (add model)"
class WeatherConfig(BaseModel):
    api_key: Optional[str] = None
    timeout: int = 15

    @field_validator("api_key", mode="before")
    @classmethod
    def _empty_to_none(cls, v):
        return _empty_str_to_none(v)
```

```python title="src/config.py (add to AppConfig)"
class AppConfig(BaseModel):
    # ... existing fields ...
    weather: WeatherConfig = Field(default_factory=WeatherConfig)
```

```yaml title="config.yaml"
weather:
  api_key: "${WEATHER_API_KEY}"
  timeout: 15
```

---

## Step 4: Wire It into the Agent

Edit `src/agent.py` to import, initialize, and register your tools:

```python title="src/agent.py (modifications)"
# Add import
from .tools.weather import get_weather, get_forecast, init_weather_tools

async def create_cianaparrot_agent(config: AppConfig):
    # ... existing init calls ...

    # Initialize weather tools  # (1)!
    init_weather_tools(
        api_key=config.weather.api_key,
        timeout=config.weather.timeout,
    )

    # ... existing code ...

    # Custom tools  # (2)!
    custom_tools = [
        web_search, web_fetch,
        schedule_task, list_tasks, cancel_task,
        get_weather, get_forecast,  # <-- add here
    ]
    if config.gateway.enabled:
        custom_tools.append(host_execute)

    # ... rest of function unchanged ...
```

1. Call `init_weather_tools()` early, before building the tools list.
2. Add your tool functions to the `custom_tools` list.

---

## Step 5: Test It

### Unit test

```python title="tests/test_weather_tools.py"
import pytest
from unittest.mock import AsyncMock, patch

from src.tools.weather import get_weather, init_weather_tools


@pytest.fixture(autouse=True)
def setup_tools():
    init_weather_tools(api_key="test-key", timeout=5)


@pytest.mark.asyncio
async def test_get_weather_no_api_key():
    """Without API key, should return an error message."""
    init_weather_tools(api_key=None)
    result = await get_weather.ainvoke({"location": "London"})
    assert "not configured" in result


@pytest.mark.asyncio
async def test_get_weather_success():
    """With a mocked API response, should format weather data."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = {
        "location": {"name": "London", "country": "UK"},
        "current": {
            "temp_c": 15, "temp_f": 59,
            "condition": {"text": "Partly cloudy"},
            "humidity": 72, "wind_kph": 20, "wind_dir": "SW",
        },
    }

    with patch("src.tools.weather.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=AsyncMock(
            get=AsyncMock(return_value=mock_response)
        ))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await get_weather.ainvoke({"location": "London"})
        assert "London" in result
        assert "15" in result
```

### Run the tests

```bash
make test
```

### Manual test via Telegram

Send a message like:

> What's the weather in Tokyo?

The agent should call `get_weather` and return the current conditions.

---

## Tool Design Guidelines

!!! abstract "Best practices"
    - **Return strings**: Tools must return a string that the agent includes in its response context.
    - **Handle errors gracefully**: Return human-readable error messages instead of raising exceptions. The agent can then relay the error to the user.
    - **Limit output size**: Truncate large outputs (the existing tools use `MAX_OUTPUT_LENGTH = 15_000`).
    - **Use descriptive docstrings**: The agent sees the tool name, docstring, and parameter types. Be specific about what each parameter accepts.
    - **Keep init separate**: The `init_*()` function runs once at startup. The `@tool` functions run per-invocation. Never put slow initialization inside a tool function.

---

## Summary

| Step | What You Did |
|------|-------------|
| 1 | Reviewed the module-level init pattern |
| 2 | Created `src/tools/weather.py` with `init_weather_tools()` and `@tool` functions |
| 3 | (Optional) Added a config model for API keys and settings |
| 4 | Wired the tools into `src/agent.py` |
| 5 | Wrote tests and verified end-to-end |
