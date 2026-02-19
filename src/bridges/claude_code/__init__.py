"""Claude Code bridge package."""

import logging

from .bridge import ClaudeCodeBridge

logger = logging.getLogger(__name__)


async def setup_bridge(config, channel) -> None:
    """Wire Claude Code bridge to a channel, if enabled.

    Handles bridge creation, availability check, and mode handler registration.
    """
    if not config.claude_code.enabled:
        return

    # Lazy import to avoid circular deps: handler → channel → __init__
    from ...channels.telegram.handlers.claude_code import ClaudeCodeHandler

    bridge = ClaudeCodeBridge(config)
    available, version = await bridge.check_available()
    if available:
        logger.info("Claude Code bridge ready: %s", version)
    else:
        logger.warning("Claude Code bridge not reachable: %s", version)

    channel.register_mode_handler(lambda app, send: ClaudeCodeHandler(bridge, app, send))
