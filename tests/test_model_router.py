"""Tests for src.tools.model_router — RoutingChatModel, switch_model, tier helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import SystemMessage

from src.tools.model_router import (
    RoutingChatModel,
    _active_tier,
    _inject_tier_note,
    get_tier_model,
    init_model_router_tools,
    reset_active_tier,
    set_active_tier,
    switch_model,
)
from src.tools import model_router as mr_module


class TestInitModelRouterTools:
    def test_sets_globals(self):
        mock_lite = MagicMock()
        mock_expert = MagicMock()
        tier_models = {"lite": mock_lite, "expert": mock_expert}

        init_model_router_tools(tier_models, default_tier="lite")

        assert mr_module._tier_models is tier_models
        assert mr_module._available_tiers == ["expert", "lite"]
        assert mr_module._default_tier == "lite"

    def test_empty_tiers(self):
        init_model_router_tools({})

        assert mr_module._tier_models == {}
        assert mr_module._available_tiers == []

    def test_default_tier_defaults_to_standard(self):
        init_model_router_tools({"standard": MagicMock()})

        assert mr_module._default_tier == "standard"


class TestGetTierModel:
    def test_returns_model_for_valid_tier(self):
        mock_model = MagicMock()
        init_model_router_tools({"lite": mock_model})

        assert get_tier_model("lite") is mock_model

    def test_returns_none_for_unknown_tier(self):
        init_model_router_tools({"lite": MagicMock()})

        assert get_tier_model("nonexistent") is None

    def test_returns_none_when_empty(self):
        init_model_router_tools({})

        assert get_tier_model("lite") is None


class TestActiveTierHelpers:
    def test_set_and_reset(self):
        set_active_tier("expert")
        assert _active_tier.get() == "expert"

        reset_active_tier()
        assert _active_tier.get() is None

    def test_default_is_none(self):
        reset_active_tier()
        assert _active_tier.get() is None

    def test_set_overwrites(self):
        set_active_tier("lite")
        set_active_tier("expert")
        assert _active_tier.get() == "expert"


class TestSwitchModel:
    @pytest.mark.asyncio
    async def test_valid_tier_sets_contextvar(self):
        init_model_router_tools({"expert": MagicMock(), "lite": MagicMock()})

        # Call raw coroutine to test ContextVar (ainvoke copies context)
        result = await switch_model.coroutine(tier="expert")

        assert "Switched to tier 'expert'" in result
        assert _active_tier.get() == "expert"

    @pytest.mark.asyncio
    async def test_invalid_tier_returns_error(self):
        init_model_router_tools({"lite": MagicMock()})

        result = await switch_model.ainvoke({"tier": "nonexistent"})

        assert "Unknown tier" in result
        assert "nonexistent" in result
        assert "lite" in result

    @pytest.mark.asyncio
    async def test_empty_models_dict(self):
        init_model_router_tools({})

        result = await switch_model.ainvoke({"tier": "expert"})

        assert "Unknown tier" in result

    @pytest.mark.asyncio
    async def test_default_tier_is_expert(self):
        init_model_router_tools({"expert": MagicMock()})

        # Call raw coroutine to test ContextVar (ainvoke copies context)
        result = await switch_model.coroutine(tier="expert")

        assert "Switched to tier 'expert'" in result
        assert _active_tier.get() == "expert"


class TestRoutingChatModel:
    def _make_mock_model(self, content="response"):
        """Create a mock BaseChatModel with _generate and _agenerate."""
        mock = MagicMock()
        mock_result = MagicMock()
        mock._generate.return_value = mock_result
        mock._agenerate = AsyncMock(return_value=mock_result)
        return mock

    def test_generate_uses_default_tier(self):
        mock_standard = self._make_mock_model()
        mock_expert = self._make_mock_model()

        router = RoutingChatModel(
            tier_models={"standard": mock_standard, "expert": mock_expert},
            default_tier="standard",
        )
        reset_active_tier()

        router._generate([])

        mock_standard._generate.assert_called_once()
        mock_expert._generate.assert_not_called()

    def test_generate_uses_active_tier(self):
        mock_standard = self._make_mock_model()
        mock_expert = self._make_mock_model()

        router = RoutingChatModel(
            tier_models={"standard": mock_standard, "expert": mock_expert},
            default_tier="standard",
        )
        set_active_tier("expert")

        router._generate([])

        mock_expert._generate.assert_called_once()
        mock_standard._generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_agenerate_uses_default_tier(self):
        mock_standard = self._make_mock_model()
        mock_expert = self._make_mock_model()

        router = RoutingChatModel(
            tier_models={"standard": mock_standard, "expert": mock_expert},
            default_tier="standard",
        )
        reset_active_tier()

        await router._agenerate([])

        mock_standard._agenerate.assert_called_once()
        mock_expert._agenerate.assert_not_called()

    @pytest.mark.asyncio
    async def test_agenerate_uses_active_tier(self):
        mock_standard = self._make_mock_model()
        mock_expert = self._make_mock_model()

        router = RoutingChatModel(
            tier_models={"standard": mock_standard, "expert": mock_expert},
            default_tier="standard",
        )
        set_active_tier("expert")

        await router._agenerate([])

        mock_expert._agenerate.assert_called_once()
        mock_standard._agenerate.assert_not_called()

    def test_invalid_active_tier_falls_back_to_default(self):
        mock_standard = self._make_mock_model()

        router = RoutingChatModel(
            tier_models={"standard": mock_standard},
            default_tier="standard",
        )
        set_active_tier("nonexistent")

        router._generate([])

        mock_standard._generate.assert_called_once()

    def test_llm_type(self):
        router = RoutingChatModel(
            tier_models={"standard": MagicMock()},
            default_tier="standard",
        )
        assert router._llm_type == "routing"

    def test_no_valid_model_raises(self):
        router = RoutingChatModel(
            tier_models={},
            default_tier="standard",
        )
        reset_active_tier()

        with pytest.raises(ValueError, match="No model for tier"):
            router._generate([])

    def test_bind_tools_pre_binds_all_tiers(self):
        """bind_tools should call bind_tools on ALL tier models."""
        mock_standard = self._make_mock_model()
        mock_standard.bind_tools = MagicMock(return_value=MagicMock())
        mock_expert = self._make_mock_model()
        mock_expert.bind_tools = MagicMock(return_value=MagicMock())

        router = RoutingChatModel(
            tier_models={"standard": mock_standard, "expert": mock_expert},
            default_tier="standard",
        )
        reset_active_tier()

        router.bind_tools(["tool1"])
        mock_standard.bind_tools.assert_called_once_with(["tool1"])
        mock_expert.bind_tools.assert_called_once_with(["tool1"])

    @pytest.mark.asyncio
    async def test_bind_tools_resolves_tier_dynamically(self):
        """The RunnableLambda returned by bind_tools should resolve tier at invoke time."""
        mock_standard_bound = AsyncMock(return_value=MagicMock())
        mock_expert_bound = AsyncMock(return_value=MagicMock())

        mock_standard = self._make_mock_model()
        mock_standard.bind_tools = MagicMock(return_value=MagicMock(ainvoke=mock_standard_bound))
        mock_expert = self._make_mock_model()
        mock_expert.bind_tools = MagicMock(return_value=MagicMock(ainvoke=mock_expert_bound))

        router = RoutingChatModel(
            tier_models={"standard": mock_standard, "expert": mock_expert},
            tier_labels={"standard": "openai:gpt-4o", "expert": "openai:gpt-5"},
            default_tier="standard",
        )

        pipeline = router.bind_tools(["tool1"])

        # Default tier → standard
        reset_active_tier()
        await pipeline.ainvoke([SystemMessage(content="test")])
        mock_standard_bound.assert_called_once()
        mock_expert_bound.assert_not_called()

        mock_standard_bound.reset_mock()

        # Switch to expert → expert
        set_active_tier("expert")
        await pipeline.ainvoke([SystemMessage(content="test")])
        mock_expert_bound.assert_called_once()
        mock_standard_bound.assert_not_called()


class TestInjectTierNote:
    def test_appends_to_system_message(self):
        messages = [SystemMessage(content="You are helpful.")]
        result = _inject_tier_note(messages, "standard", "openai:gpt-4o")

        assert len(result) == 1
        assert "openai:gpt-4o" in result[0].content
        assert "tier: standard" in result[0].content
        assert result[0].content.startswith("You are helpful.")

    def test_empty_messages_unchanged(self):
        assert _inject_tier_note([], "standard", "openai:gpt-4o") == []

    def test_does_not_mutate_original(self):
        original = [SystemMessage(content="Original")]
        result = _inject_tier_note(original, "standard", "openai:gpt-4o")
        assert original[0].content == "Original"
        assert result[0].content != "Original"

    def test_no_system_message_skips(self):
        """If first message is not SystemMessage, don't inject."""
        from langchain_core.messages import HumanMessage
        messages = [HumanMessage(content="hello")]
        result = _inject_tier_note(messages, "standard", "openai:gpt-4o")
        assert result[0].content == "hello"

    def test_list_content_appends_to_last_text_block(self):
        """SystemMessage with list content (multimodal) should work."""
        messages = [SystemMessage(content=[
            {"type": "text", "text": "You are helpful."},
        ])]
        result = _inject_tier_note(messages, "standard", "openai:gpt-4o")
        assert isinstance(result[0].content, list)
        assert "openai:gpt-4o" in result[0].content[0]["text"]
        assert result[0].content[0]["text"].startswith("You are helpful.")
