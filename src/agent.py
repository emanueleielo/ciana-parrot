"""Agent setup - creates DeepAgents agent with all middleware and tools."""

import logging
import re
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.chat_models import init_chat_model
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from .tools.web import web_search, web_fetch, init_web_tools
from .tools.cron import schedule_task, list_tasks, cancel_task, init_cron_tools

logger = logging.getLogger(__name__)

# Shell command blocklist
BLOCKED_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"mkfs",
    r"dd\s+if=",
    r"format\s+",
    r"shutdown",
    r"reboot",
    r"poweroff",
    r"/dev/sd[a-z]",
    r":()\s*\{.*\|.*&\s*\}\s*;",  # fork bomb
    r">\s*/dev/sd",
    r"chmod\s+-R\s+777\s+/",
]
_BLOCKED_RE = re.compile("|".join(BLOCKED_PATTERNS))


def _is_command_safe(command: str) -> bool:
    """Check if a shell command is safe to execute."""
    return not _BLOCKED_RE.search(command)


async def create_cianaparrot_agent(config: dict):
    """Create and return the main CianaParrot agent.

    Returns:
        tuple: (agent, checkpointer, mcp_client_or_None)
    """
    # Initialize tool configs
    init_web_tools(config)
    init_cron_tools(config)

    # LLM provider
    provider_cfg = config["provider"]
    provider_name = provider_cfg["name"]
    model_name = provider_cfg["model"]

    model_kwargs = {}
    if provider_cfg.get("temperature") is not None:
        model_kwargs["temperature"] = provider_cfg["temperature"]
    if provider_cfg.get("max_tokens") is not None:
        model_kwargs["max_tokens"] = provider_cfg["max_tokens"]
    if provider_cfg.get("base_url"):
        model_kwargs["base_url"] = provider_cfg["base_url"]

    model = init_chat_model(
        f"{provider_name}:{model_name}",
        **model_kwargs,
    )
    logger.info("LLM provider: %s:%s", provider_name, model_name)

    # Workspace
    workspace = config["agent"]["workspace"]
    Path(workspace).mkdir(parents=True, exist_ok=True)
    Path(workspace, "sessions").mkdir(parents=True, exist_ok=True)

    # Memory files
    memory_files = []
    for fname in ["IDENTITY.md", "AGENT.md", "MEMORY.md"]:
        fpath = Path(workspace, fname)
        if fpath.exists():
            memory_files.append(str(fpath))
            logger.info("Memory file loaded: %s", fpath)

    # Skills directory
    skills_dirs = []
    skills_cfg = config.get("skills", {})
    if skills_cfg.get("enabled", True):
        skills_dir = skills_cfg.get("directory", "./skills")
        if Path(skills_dir).exists():
            skills_dirs.append(skills_dir)
            logger.info("Skills directory: %s", skills_dir)

    # Custom tools
    custom_tools = [web_search, web_fetch, schedule_task, list_tasks, cancel_task]

    # MCP tools
    mcp_client = None
    mcp_tools = []
    mcp_servers = config.get("mcp_servers", {})
    if mcp_servers:
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            mcp_client = MultiServerMCPClient(mcp_servers)
            mcp_tools = await mcp_client.get_tools()
            logger.info("MCP tools loaded: %d", len(mcp_tools))
        except Exception as e:
            logger.warning("Failed to load MCP tools: %s", e)

    # Checkpointer (SQLite for persistence across restarts)
    db_path = str(Path(workspace, "checkpoints.db"))
    conn = await aiosqlite.connect(db_path)
    checkpointer = AsyncSqliteSaver(conn)
    await checkpointer.setup()

    # Create agent
    all_tools = custom_tools + mcp_tools

    agent = create_deep_agent(
        model=model,
        memory=memory_files,
        skills=skills_dirs if skills_dirs else None,
        tools=all_tools,
        backend=FilesystemBackend(root_dir=workspace, virtual_mode=True),
        checkpointer=checkpointer,
    )

    logger.info(
        "Agent created: %d custom tools, %d MCP tools, %d memory files, %d skill dirs",
        len(custom_tools), len(mcp_tools), len(memory_files), len(skills_dirs),
    )

    return agent, checkpointer, mcp_client
