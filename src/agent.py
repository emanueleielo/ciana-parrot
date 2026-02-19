"""Agent setup - creates DeepAgents agent with all middleware and tools."""

import logging
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.chat_models import init_chat_model
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from .config import AppConfig
from .tools.web import web_search, web_fetch, init_web_tools
from .tools.cron import schedule_task, list_tasks, cancel_task, init_cron_tools

logger = logging.getLogger(__name__)


async def create_cianaparrot_agent(config: AppConfig):
    """Create and return the main CianaParrot agent.

    Returns:
        tuple: (agent, checkpointer, mcp_client_or_None)
    """
    # Initialize tool configs
    init_web_tools(config.web)
    init_cron_tools(config.scheduler)

    # LLM provider
    provider_name = config.provider.name
    model_name = config.provider.model

    model_kwargs = {}
    if config.provider.temperature is not None:
        model_kwargs["temperature"] = config.provider.temperature
    if config.provider.max_tokens is not None:
        model_kwargs["max_tokens"] = config.provider.max_tokens
    if config.provider.base_url:
        model_kwargs["base_url"] = config.provider.base_url

    model = init_chat_model(
        f"{provider_name}:{model_name}",
        **model_kwargs,
    )
    logger.info("LLM provider: %s:%s", provider_name, model_name)

    # Workspace
    workspace = config.agent.workspace
    Path(workspace).mkdir(parents=True, exist_ok=True)
    Path(workspace, "sessions").mkdir(parents=True, exist_ok=True)

    # Memory files (paths relative to workspace, resolved by FilesystemBackend)
    memory_files = []
    for fname in ["IDENTITY.md", "AGENT.md", "MEMORY.md"]:
        fpath = Path(workspace, fname)
        if fpath.exists():
            memory_files.append(fname)
            logger.info("Memory file loaded: %s", fpath)

    # Skills directory
    skills_dirs = []
    if config.skills.enabled:
        skills_dir = config.skills.directory
        if Path(skills_dir).exists():
            skills_dirs.append(skills_dir)
            logger.info("Skills directory: %s", skills_dir)

    # Custom tools
    custom_tools = [web_search, web_fetch, schedule_task, list_tasks, cancel_task]

    # MCP tools
    mcp_client = None
    mcp_tools = []
    if config.mcp_servers:
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            mcp_client = MultiServerMCPClient(config.mcp_servers)
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
