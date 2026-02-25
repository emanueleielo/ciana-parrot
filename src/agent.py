"""Agent setup - creates DeepAgents agent with all middleware and tools."""

import logging
from pathlib import Path

from deepagents import create_deep_agent
from .backend import WorkspaceShellBackend
from langchain.chat_models import init_chat_model
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from . import middleware as _middleware  # noqa: F401 — patches skill YAML parser
from .config import AppConfig
from .tools.web import web_search, web_fetch, init_web_tools
from .tools.cron import schedule_task, list_tasks, cancel_task, init_cron_tools
from .tools.host import host_execute, init_host_tools
from .tools.model_router import switch_model, init_model_router_tools, RoutingChatModel
from .transcription import init_transcription

logger = logging.getLogger(__name__)


async def create_cianaparrot_agent(config: AppConfig):
    """Create and return the main CianaParrot agent.

    Returns:
        tuple: (agent, checkpointer, mcp_client_or_None)
    """
    # Initialize tool configs
    init_web_tools(config.web)
    init_cron_tools(config.scheduler)
    if config.gateway.enabled:
        init_host_tools(config.gateway)

    # Initialize transcription if enabled
    if config.transcription.enabled:
        init_transcription(config.transcription)

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

    base_model = init_chat_model(
        f"{provider_name}:{model_name}",
        **model_kwargs,
    )
    model = base_model  # may be replaced by RoutingChatModel below
    logger.info("LLM provider: %s:%s", provider_name, model_name)

    # Workspace
    workspace = config.agent.workspace
    Path(workspace).mkdir(parents=True, exist_ok=True)

    # Memory files (paths relative to workspace, resolved by FilesystemBackend)
    memory_files = []
    for fname in ["IDENTITY.md", "AGENT.md", "MEMORY.md"]:
        fpath = Path(workspace, fname)
        if fpath.exists():
            memory_files.append(fname)
            logger.info("Memory file loaded: %s", fpath)

    # Skills directory (virtual path relative to workspace)
    skills_dirs = []
    if config.skills.enabled:
        skills_path = Path(workspace, "skills")
        skills_path.mkdir(parents=True, exist_ok=True)
        skills_dirs.append("skills")
        logger.info("Skills directory: %s (workspace-relative)", skills_path)

    # Custom tools
    custom_tools = [web_search, web_fetch, schedule_task, list_tasks, cancel_task]
    if config.gateway.enabled:
        custom_tools.append(host_execute)

    # Model router tiers
    tier_models: dict = {}

    if config.model_router.enabled and config.model_router.tiers:
        default_tier = config.model_router.default_tier
        for tier_name, tier_cfg in config.model_router.tiers.items():
            try:
                tier_kwargs = {}
                if tier_cfg.temperature is not None:
                    tier_kwargs["temperature"] = tier_cfg.temperature
                if tier_cfg.max_tokens is not None:
                    tier_kwargs["max_tokens"] = tier_cfg.max_tokens
                if tier_cfg.base_url:
                    tier_kwargs["base_url"] = tier_cfg.base_url
                tier_models[tier_name] = init_chat_model(
                    f"{tier_cfg.name}:{tier_cfg.model}", **tier_kwargs
                )
                logger.info("Model tier initialized: %s (%s:%s)", tier_name, tier_cfg.name, tier_cfg.model)
            except Exception as e:
                logger.warning("Failed to init tier '%s': %s", tier_name, e)

        if tier_models:
            init_model_router_tools(tier_models, default_tier=default_tier)
            custom_tools.append(switch_model)
            # Build label map for system prompt injection
            tier_labels = {
                name: f"{cfg.name}:{cfg.model}"
                for name, cfg in config.model_router.tiers.items()
                if name in tier_models
            }
            # Replace base model with RoutingChatModel
            model = RoutingChatModel(
                tier_models=tier_models,
                tier_labels=tier_labels,
                default_tier=default_tier,
            )
            logger.info("RoutingChatModel active (default_tier=%s, tiers=%s)",
                        default_tier, sorted(tier_models.keys()))

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

    # Checkpointer (SQLite in data_dir — outside agent sandbox)
    data_dir = config.agent.data_dir
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    db_path = str(Path(data_dir, "checkpoints.db"))
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
        backend=WorkspaceShellBackend(root_dir=workspace, virtual_mode=True),
        checkpointer=checkpointer,
    )

    logger.info(
        "Agent created: %d custom tools, %d MCP tools, %d memory files, %d skill dirs",
        len(custom_tools), len(mcp_tools), len(memory_files), len(skills_dirs),
    )

    return agent, checkpointer, mcp_client
