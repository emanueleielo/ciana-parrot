"""Tests for _render_cc_response — compact + details output."""

from src.bridges.claude_code.bridge import (
    CCResponse,
    TextEvent,
    ThinkingEvent,
    ToolCallEvent,
)
from src.channels.telegram.handlers.claude_code import _render_cc_response


class TestRenderCcResponse:
    def test_error_response(self):
        resp = CCResponse(error="Something went wrong")
        compact, details = _render_cc_response(resp)
        assert "error" in compact.lower()
        assert "Something went wrong" in compact
        assert details == ""

    def test_multiline_error(self):
        resp = CCResponse(error="line1\nline2")
        compact, details = _render_cc_response(resp)
        assert "```" in compact
        assert "line1" in compact

    def test_text_only(self):
        resp = CCResponse(events=[TextEvent(text="Hello world")])
        compact, details = _render_cc_response(resp)
        assert compact == "Hello world"
        assert details == ""

    def test_tool_call_compact(self):
        resp = CCResponse(events=[
            ToolCallEvent(
                tool_id="t1", name="Read", input_summary="file.py",
                result_text="content", is_error=False,
            ),
            TextEvent(text="Done"),
        ])
        compact, details = _render_cc_response(resp)
        assert "Read" in compact
        assert "file.py" in compact
        assert "Done" in compact

    def test_tool_details(self):
        resp = CCResponse(events=[
            ToolCallEvent(
                tool_id="t1", name="Bash", input_summary="ls",
                result_text="file1.txt\nfile2.txt", is_error=False,
            ),
        ])
        compact, details = _render_cc_response(resp)
        assert "Bash" in compact
        assert "file1.txt" in details
        assert "file2.txt" in details

    def test_tool_error_inline(self):
        resp = CCResponse(events=[
            ToolCallEvent(
                tool_id="t1", name="Bash", input_summary="bad-cmd",
                result_text="command not found", is_error=True,
            ),
        ])
        compact, details = _render_cc_response(resp)
        assert "\u274c" in compact
        assert "command not found" in compact

    def test_thinking_event(self):
        resp = CCResponse(events=[
            ThinkingEvent(text="Let me think about this"),
            TextEvent(text="Answer"),
        ])
        compact, details = _render_cc_response(resp)
        assert "Thinking" in compact
        assert "Answer" in compact

    def test_multiple_tools(self):
        resp = CCResponse(events=[
            ToolCallEvent(
                tool_id="t1", name="Read", input_summary="a.py",
                result_text="", is_error=False,
            ),
            ToolCallEvent(
                tool_id="t2", name="Write", input_summary="b.py",
                result_text="", is_error=False,
            ),
            TextEvent(text="All done"),
        ])
        compact, details = _render_cc_response(resp)
        assert "Read" in compact
        assert "Write" in compact
        assert "All done" in compact

    def test_empty_events(self):
        resp = CCResponse(events=[])
        compact, details = _render_cc_response(resp)
        assert compact == "(empty response)"

    def test_tool_without_result(self):
        resp = CCResponse(events=[
            ToolCallEvent(
                tool_id="t1", name="Glob", input_summary="*.py",
                result_text="", is_error=False,
            ),
        ])
        compact, details = _render_cc_response(resp)
        assert "Glob" in compact
        # Details should show checkmark for no-result tools
        assert "\u2714" in details

    def test_tool_no_summary(self):
        resp = CCResponse(events=[
            ToolCallEvent(
                tool_id="t1", name="CustomTool", input_summary="",
                result_text="output", is_error=False,
            ),
        ])
        compact, details = _render_cc_response(resp)
        assert "CustomTool" in compact
