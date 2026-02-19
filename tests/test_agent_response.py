"""Tests for src.agent_response — extract_agent_response with events."""

from unittest.mock import MagicMock

from src.agent_response import AgentResponse, extract_agent_response
from src.events import TextEvent, ToolCallEvent, ThinkingEvent


class TestExtractAgentResponse:
    def test_simple_text(self):
        msg = MagicMock(type="ai", content="Hello world", tool_calls=[])
        result = {"messages": [msg]}
        resp = extract_agent_response(result)
        assert resp.text == "Hello world"
        assert len(resp.events) == 1
        assert isinstance(resp.events[0], TextEvent)
        assert resp.events[0].text == "Hello world"

    def test_with_tool_calls_and_results(self):
        human = MagicMock(type="human", content="search test")
        ai_call = MagicMock(
            type="ai",
            content="",
            tool_calls=[
                {"name": "web_search", "args": {"query": "test"}, "id": "tc1"},
            ],
        )
        tool_result = MagicMock(
            type="tool",
            content="Search results here",
            tool_call_id="tc1",
            status="success",
        )
        ai_final = MagicMock(type="ai", content="Here are the results", tool_calls=[])
        result = {"messages": [human, ai_call, tool_result, ai_final]}
        resp = extract_agent_response(result)
        assert resp.text == "Here are the results"
        assert len(resp.events) == 2  # ToolCallEvent + TextEvent
        assert isinstance(resp.events[0], ToolCallEvent)
        assert resp.events[0].name == "web_search"
        assert resp.events[0].result_text == "Search results here"
        assert resp.events[0].is_error is False
        assert isinstance(resp.events[1], TextEvent)

    def test_tool_call_error(self):
        human = MagicMock(type="human", content="do something")
        ai_call = MagicMock(
            type="ai",
            content="",
            tool_calls=[
                {"name": "web_fetch", "args": {"url": "http://bad"}, "id": "tc1"},
            ],
        )
        tool_result = MagicMock(
            type="tool",
            content="Connection error",
            tool_call_id="tc1",
            status="error",
        )
        ai_final = MagicMock(type="ai", content="Sorry, that failed", tool_calls=[])
        result = {"messages": [human, ai_call, tool_result, ai_final]}
        resp = extract_agent_response(result)
        tools = [e for e in resp.events if isinstance(e, ToolCallEvent)]
        assert len(tools) == 1
        assert tools[0].is_error is True
        assert tools[0].result_text == "Connection error"

    def test_multiple_tool_calls(self):
        human = MagicMock(type="human", content="go")
        ai = MagicMock(
            type="ai",
            content="",
            tool_calls=[
                {"name": "tool_a", "args": {}, "id": "a1"},
                {"name": "tool_b", "args": {"x": 1}, "id": "b1"},
            ],
        )
        tr_a = MagicMock(type="tool", content="result_a", tool_call_id="a1", status="success")
        tr_b = MagicMock(type="tool", content="result_b", tool_call_id="b1", status="success")
        ai_final = MagicMock(type="ai", content="Done", tool_calls=[])
        result = {"messages": [human, ai, tr_a, tr_b, ai_final]}
        resp = extract_agent_response(result)
        tools = [e for e in resp.events if isinstance(e, ToolCallEvent)]
        assert len(tools) == 2
        assert tools[0].name == "tool_a"
        assert tools[1].name == "tool_b"

    def test_no_tool_calls_attr(self):
        """Messages without tool_calls attribute should be skipped."""
        msg = MagicMock(spec=["content", "type"])
        msg.content = "Just text"
        msg.type = "ai"
        result = {"messages": [msg]}
        resp = extract_agent_response(result)
        assert resp.text == "Just text"
        assert len(resp.events) == 1

    def test_last_text_event_used(self):
        human = MagicMock(type="human", content="hi")
        msg1 = MagicMock(type="ai", content="First", tool_calls=[])
        msg2 = MagicMock(type="ai", content="Last", tool_calls=[])
        result = {"messages": [human, msg1, msg2]}
        resp = extract_agent_response(result)
        assert resp.text == "Last"

    def test_tool_call_missing_name(self):
        human = MagicMock(type="human", content="go")
        msg = MagicMock(
            type="ai",
            content="",
            tool_calls=[{"args": {}, "id": "x1"}],
        )
        tr = MagicMock(type="tool", content="ok", tool_call_id="x1", status="success")
        result = {"messages": [human, msg, tr]}
        resp = extract_agent_response(result)
        tools = [e for e in resp.events if isinstance(e, ToolCallEvent)]
        assert tools[0].name == "unknown"

    def test_agent_response_dataclass(self):
        resp = AgentResponse(text="hi")
        assert resp.text == "hi"
        assert resp.events == []

    def test_empty_messages(self):
        resp = extract_agent_response({"messages": []})
        assert resp.text == ""
        assert resp.events == []

    def test_no_messages_key(self):
        resp = extract_agent_response({})
        assert resp.text == ""
        assert resp.events == []

    def test_list_content_with_thinking(self):
        human = MagicMock(type="human", content="think about this")
        msg = MagicMock(
            type="ai",
            content=[
                {"type": "thinking", "thinking": "Let me consider..."},
                {"type": "text", "text": "Here's my answer"},
            ],
            tool_calls=[],
        )
        result = {"messages": [human, msg]}
        resp = extract_agent_response(result)
        assert any(isinstance(e, ThinkingEvent) for e in resp.events)
        assert any(isinstance(e, TextEvent) for e in resp.events)
        thinking = [e for e in resp.events if isinstance(e, ThinkingEvent)]
        assert "consider" in thinking[0].text

    def test_input_summary_generated(self):
        human = MagicMock(type="human", content="read file")
        ai = MagicMock(
            type="ai",
            content="",
            tool_calls=[
                {"name": "Read", "args": {"file_path": "/src/main.py"}, "id": "r1"},
            ],
        )
        tr = MagicMock(type="tool", content="file content", tool_call_id="r1", status="success")
        result = {"messages": [human, ai, tr]}
        resp = extract_agent_response(result)
        tools = [e for e in resp.events if isinstance(e, ToolCallEvent)]
        assert tools[0].input_summary == "main.py"
