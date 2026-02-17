"""CianaParrot entry point - wires channels, agent, and scheduler."""

import asyncio
import logging
import signal

from .config import load_config
from .agent import create_cianaparrot_agent
from .router import MessageRouter
from .scheduler import Scheduler
from .channels.telegram import TelegramChannel

logger = logging.getLogger(__name__)


async def main() -> None:
    # Load config
    config = load_config()

    # Logging
    log_level = config.get("logging", {}).get("level", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("CianaParrot starting...")

    # Create agent
    agent, checkpointer, mcp_client = await create_cianaparrot_agent(config)
    logger.info("Agent ready")

    # Router
    router = MessageRouter(agent, config)

    # Channels
    channels = []
    channels_config = config.get("channels", {})

    if channels_config.get("telegram", {}).get("enabled"):
        tg_config = channels_config["telegram"]
        tg = TelegramChannel(tg_config)

        async def tg_callback(msg):
            return await router.handle_message(msg, tg_config)

        tg.on_message(tg_callback)
        channels.append(tg)
        logger.info("Telegram channel configured")

    # Start channels
    for ch in channels:
        await ch.start()
        logger.info("Channel started: %s", ch.name)

    # Scheduler (with channel references for sending results)
    scheduler = None
    if config.get("scheduler", {}).get("enabled"):
        channels_map = {ch.name: ch for ch in channels}
        scheduler = Scheduler(agent, config, channels=channels_map)
        await scheduler.start()

    logger.info("CianaParrot is running. Press Ctrl+C to stop.")

    # Graceful shutdown
    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    # Wait for shutdown
    await stop_event.wait()

    # Cleanup
    logger.info("Shutting down...")
    if scheduler:
        await scheduler.stop()
    for ch in channels:
        await ch.stop()
    if mcp_client:
        try:
            await mcp_client.close()
        except (OSError, RuntimeError):
            logger.debug("MCP client close failed (already closed or loop shutdown)")

    logger.info("CianaParrot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
