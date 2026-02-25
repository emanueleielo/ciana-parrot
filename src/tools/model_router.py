"""Model router — RoutingChatModel + switch_model tool for in-chat tier switching."""

import logging
from contextvars import ContextVar
from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.outputs import ChatResult
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool
from pydantic import ConfigDict

logger = logging.getLogger(__name__)

# ContextVar: per-asyncio-task active tier (None = use default)
_active_tier: ContextVar[str | None] = ContextVar("_active_tier", default=None)

# Module-level state, set by init_model_router_tools()
_tier_models: dict[str, Any] = {}
_available_tiers: list[str] = []
_default_tier: str = "standard"


def init_model_router_tools(
    tier_models: dict[str, Any],
    default_tier: str = "standard",
) -> None:
    """Initialize model router with pre-created tier models."""
    global _tier_models, _available_tiers, _default_tier
    _tier_models = tier_models
    _available_tiers = sorted(tier_models.keys())
    _default_tier = default_tier


def get_tier_model(tier: str):
    """Return the LLM for a tier, or None if not available."""
    return _tier_models.get(tier)


def set_active_tier(tier: str) -> None:
    """Set the active tier for the current asyncio task (used by scheduler)."""
    _active_tier.set(tier)


def reset_active_tier() -> None:
    """Reset the active tier to None (default) for the current asyncio task."""
    _active_tier.set(None)


def _inject_tier_note(messages: list, tier: str, label: str) -> list:
    """Append a model-tier note to the system message."""
    if not messages or not isinstance(messages[0], SystemMessage):
        return messages
    note = f"\n\n[Current model: {label} (tier: {tier})]"
    modified = list(messages)
    content = modified[0].content
    if isinstance(content, str):
        modified[0] = SystemMessage(content=content + note)
    elif isinstance(content, list):
        # Multimodal content blocks — append note to last text block
        new_content = list(content)
        for i in range(len(new_content) - 1, -1, -1):
            if isinstance(new_content[i], dict) and new_content[i].get("type") == "text":
                new_content[i] = {**new_content[i], "text": new_content[i]["text"] + note}
                break
            elif isinstance(new_content[i], str):
                new_content[i] = new_content[i] + note
                break
        else:
            new_content.append({"type": "text", "text": note.strip()})
        modified[0] = SystemMessage(content=new_content)
    return modified


class RoutingChatModel(BaseChatModel):
    """Chat model that delegates to the active tier's underlying model.

    Uses a ContextVar (_active_tier) to determine which tier model to use.
    Falls back to default_tier when no tier is explicitly set.
    """

    tier_models: dict[str, Any]
    tier_labels: dict[str, str] = {}  # tier_name -> "provider:model" for system prompt
    default_tier: str = "standard"

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def _llm_type(self) -> str:
        return "routing"

    def _resolve_tier(self) -> str:
        """Return the effective tier name (active or default)."""
        tier = _active_tier.get() or self.default_tier
        if tier not in self.tier_models:
            tier = self.default_tier
        return tier

    def _current_model(self) -> BaseChatModel:
        """Resolve the current tier's model."""
        tier = self._resolve_tier()
        model = self.tier_models.get(tier)
        if model is None:
            raise ValueError(
                f"No model for tier '{tier}' (default='{self.default_tier}'). "
                f"Available: {sorted(self.tier_models.keys())}"
            )
        return model

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        """Pre-bind tools on ALL tiers, resolve the active tier dynamically.

        Returns a RunnableLambda that, on each invocation:
        1. Reads _active_tier to pick the correct tier
        2. Injects the tier note into the system message
        3. Delegates to that tier's pre-bound model
        """
        pre_bound = {}
        for name, model in self.tier_models.items():
            pre_bound[name] = model.bind_tools(tools, **kwargs)

        tier_labels = self.tier_labels
        default_tier = self.default_tier

        async def _route_and_invoke(messages: list) -> Any:
            tier = _active_tier.get() or default_tier
            if tier not in pre_bound:
                tier = default_tier
            bound = pre_bound.get(tier)
            if bound is None:
                raise ValueError(
                    f"No model for tier '{tier}'. "
                    f"Available: {sorted(pre_bound.keys())}"
                )
            label = tier_labels.get(tier, tier)
            injected = _inject_tier_note(messages, tier, label)
            return await bound.ainvoke(injected)

        return RunnableLambda(_route_and_invoke)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._current_model()._generate(
            messages, stop=stop, run_manager=run_manager, **kwargs
        )

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        return await self._current_model()._agenerate(
            messages, stop=stop, run_manager=run_manager, **kwargs
        )


@tool
async def switch_model(tier: str = "expert") -> str:
    """Switch to a different model tier for the rest of this conversation turn.

    Use this when the current task needs a more capable model:
    - tier 'advanced': Complex coding, multi-step analysis, detailed writing
    - tier 'expert': Architecture design, theorem proving, nuanced reasoning

    Do NOT switch when:
    - The task is simple (greetings, status, factual lookups)
    - You're already on the right tier for the task

    The switch takes effect on the NEXT step — the model will have full access
    to all tools, memory, and conversation history.

    Args:
        tier: Model tier to switch to — one of: lite, standard, advanced, expert.
    """
    if tier not in _tier_models:
        return f"Unknown tier '{tier}'. Available: {_available_tiers}"

    _active_tier.set(tier)
    logger.info("Model tier switched to '%s'", tier)
    return f"Switched to tier '{tier}'. The next step will use this model."
