"""Host execution tool — runs commands on the host via the secure gateway."""

import logging
import shlex
from typing import Optional

from langchain_core.tools import tool

from ..config import GatewayConfig
from ..gateway.client import GatewayClient

logger = logging.getLogger(__name__)

MAX_OUTPUT_LENGTH = 15_000

# Module-level state, set by init_host_tools()
_gateway_client: Optional[GatewayClient] = None
_available_bridges: dict[str, list[str]] = {}
_default_timeout: int = 30


def init_host_tools(config: GatewayConfig) -> None:
    """Initialize host tools with gateway config."""
    global _gateway_client, _available_bridges, _default_timeout
    if config.url:
        _gateway_client = GatewayClient(config.url, config.token)
    _available_bridges = {
        name: bdef.allowed_commands for name, bdef in config.bridges.items()
    }
    _default_timeout = config.default_timeout


@tool
async def host_execute(bridge: str, command: str, timeout: int = 0) -> str:
    """Execute a command on the host via the secure gateway.

    Args:
        bridge: Bridge name ("apple-notes", "spotify", "apple-reminders", etc.)
        command: Shell command string (e.g. "memo list", "spogo play 'song name'")
        timeout: Seconds. 0 = use default.
    """
    if _gateway_client is None:
        return "Error: host gateway not configured."

    if bridge not in _available_bridges:
        available = ", ".join(sorted(_available_bridges.keys())) or "(none)"
        return f"Error: unknown bridge '{bridge}'. Available: {available}"

    try:
        cmd_list = shlex.split(command)
    except ValueError as e:
        return f"Error: invalid command syntax: {e}"

    if not cmd_list:
        return "Error: empty command."

    effective_timeout = timeout if timeout > 0 else _default_timeout

    result = await _gateway_client.execute(
        bridge=bridge,
        cmd=cmd_list,
        timeout=effective_timeout,
    )

    if result.error:
        return f"Error: {result.error}"

    output = result.stdout.strip()
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if stderr:
            output = f"Command failed (exit {result.returncode}):\n{stderr}"
        elif output:
            output = f"Command failed (exit {result.returncode}):\n{output}"
        else:
            output = f"Command failed with exit code {result.returncode}."

    if not output:
        return "(no output)"

    if len(output) > MAX_OUTPUT_LENGTH:
        output = output[:MAX_OUTPUT_LENGTH] + "\n\n... (truncated)"

    return output
