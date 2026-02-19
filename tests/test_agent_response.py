"""Tests for src.agent_response — extract_agent_response."""

from unittest.mock import MagicMock

from src.agent_response import AgentResponse, extract_agent_response


class TestExtractAgentResponse:
    def test_simple_text(self):
        msg = MagicMock(content="Hello world", tool_calls=[])
        result = {"messages": [msg]}
        resp = extract_agent_response(result)
        assert resp.text == "Hello world"
        assert resp.tool_calls == []

    def test_with_tool_calls(self):
        msg1 = MagicMock(
            content="",
            tool_calls=[
                {"name": "web_search", "args": {"query": "test"}},
            ],
        )
        msg2 = MagicMock(content="Search result", tool_calls=[])
        result = {"messages": [msg1, msg2]}
        resp = extract_agent_response(result)
        assert resp.text == "Search result"
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0]["name"] == "web_search"

    def test_multiple_tool_calls(self):
        msg = MagicMock(
            content="Done",
            tool_calls=[
                {"name": "tool_a", "args": {}},
                {"name": "tool_b", "args": {"x": 1}},
            ],
        )
        result = {"messages": [msg]}
        resp = extract_agent_response(result)
        assert len(resp.tool_calls) == 2
        assert resp.tool_calls[0]["name"] == "tool_a"
        assert resp.tool_calls[1]["name"] == "tool_b"

    def test_no_tool_calls_attr(self):
        """Messages without tool_calls attribute should be skipped."""
        msg = MagicMock(spec=["content"])
        msg.content = "Just text"
        result = {"messages": [msg]}
        resp = extract_agent_response(result)
        assert resp.text == "Just text"
        assert resp.tool_calls == []

    def test_last_message_content_used(self):
        msg1 = MagicMock(content="First", tool_calls=[])
        msg2 = MagicMock(content="Last", tool_calls=[])
        result = {"messages": [msg1, msg2]}
        resp = extract_agent_response(result)
        assert resp.text == "Last"

    def test_tool_call_missing_name(self):
        msg = MagicMock(
            content="ok",
            tool_calls=[{"args": {}}],
        )
        result = {"messages": [msg]}
        resp = extract_agent_response(result)
        assert resp.tool_calls[0]["name"] == "unknown"

    def test_agent_response_dataclass(self):
        resp = AgentResponse(text="hi")
        assert resp.text == "hi"
        assert resp.tool_calls == []

    def test_agent_response_with_tool_calls(self):
        resp = AgentResponse(text="done", tool_calls=[{"name": "t", "args": {}}])
        assert len(resp.tool_calls) == 1
