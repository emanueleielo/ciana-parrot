"""Tests for rendering internals — compact lines, grouping, collapse, detail HTML."""

from src.channels.telegram.rendering import (
    render_events,
    _build_compact_lines,
    tool_detail_html,
    thinking_detail_html,
    _tool_icon,
)
from src.events import TextEvent, ToolCallEvent, ThinkingEvent


class TestBuildCompactLines:
    def test_sub_agent_collapse(self):
        """Task (sub-agent) collapses intermediate events; only Task line and final text remain."""
        events = [
            ToolCallEvent(tool_id="t1", name="Task", input_summary="do stuff",
                          result_text="", is_error=False),
            ToolCallEvent(tool_id="t2", name="Read", input_summary="file.py",
                          result_text="content", is_error=False),
            TextEvent(text="sub-result"),
            TextEvent(text="Final answer"),
        ]
        lines = _build_compact_lines(events)
        joined = "\n\n".join(lines)
        # Task line should be present
        assert "Task" in joined
        # Intermediate Read and sub-result should be collapsed (skipped)
        assert "Read" not in joined
        assert "sub-result" not in joined
        # Final answer (last TextEvent) should be present
        assert "Final answer" in joined

    def test_grouped_consecutive_tools(self):
        """Three consecutive same-name tools are grouped into a single count line."""
        events = [
            ToolCallEvent(tool_id="t1", name="Read", input_summary="a.py",
                          result_text="", is_error=False),
            ToolCallEvent(tool_id="t2", name="Read", input_summary="b.py",
                          result_text="", is_error=False),
            ToolCallEvent(tool_id="t3", name="Read", input_summary="c.py",
                          result_text="", is_error=False),
        ]
        lines = _build_compact_lines(events)
        joined = "\n\n".join(lines)
        assert "3 calls" in joined
        assert "Read" in joined

    def test_error_tool_with_result(self):
        """An errored tool with result_text shows error icon and code block."""
        events = [
            ToolCallEvent(tool_id="t1", name="Bash", input_summary="bad-cmd",
                          result_text="command not found", is_error=True),
        ]
        lines = _build_compact_lines(events)
        joined = "\n\n".join(lines)
        assert "\u274c" in joined  # error icon
        assert "```" in joined  # code block
        assert "command not found" in joined

    def test_mixed_events(self):
        """Mixed events (thinking, tool, text) all appear in output."""
        events = [
            ThinkingEvent(text="Let me think"),
            ToolCallEvent(tool_id="t1", name="Bash", input_summary="ls",
                          result_text="file.txt", is_error=False),
            TextEvent(text="Here are the files"),
        ]
        lines = _build_compact_lines(events)
        joined = "\n\n".join(lines)
        assert "Thinking" in joined
        assert "Bash" in joined
        assert "Here are the files" in joined


class TestRenderEvents:
    def test_error_string_single_line(self):
        """Single-line error is rendered inline."""
        compact, details = render_events([], error="simple error")
        assert compact == "Error: simple error"
        assert details == []

    def test_error_string_multiline(self):
        """Multi-line error is rendered in a code block."""
        compact, details = render_events([], error="line1\nline2")
        assert "```" in compact
        assert "line1" in compact
        assert "line2" in compact
        assert details == []

    def test_empty_events(self):
        """No events and no error produces the empty-response placeholder."""
        compact, details = render_events([])
        assert compact == "(empty response)"
        assert details == []


class TestToolDetailHtml:
    def test_tool_with_result(self):
        """Tool with result_text includes a <pre> block."""
        ev = ToolCallEvent(
            tool_id="t1", name="Bash", input_summary="ls",
            result_text="file1.txt\nfile2.txt", is_error=False,
        )
        html_out = tool_detail_html(ev)
        assert "<pre>" in html_out
        assert "file1.txt" in html_out
        assert "Bash" in html_out

    def test_tool_without_result(self):
        """Tool with empty result_text shows a checkmark."""
        ev = ToolCallEvent(
            tool_id="t1", name="Glob", input_summary="*.py",
            result_text="", is_error=False,
        )
        html_out = tool_detail_html(ev)
        assert "\u2714" in html_out  # checkmark
        assert "<pre>" not in html_out

    def test_error_tool(self):
        """Errored tool shows the error icon."""
        ev = ToolCallEvent(
            tool_id="t1", name="Read", input_summary="missing.py",
            result_text="file not found", is_error=True,
        )
        html_out = tool_detail_html(ev)
        assert "\u274c" in html_out  # error icon
        assert "<pre>" in html_out
        assert "file not found" in html_out


class TestThinkingDetailHtml:
    def test_thinking_truncation(self):
        """Thinking text longer than 1500 chars is truncated."""
        long_text = "A" * 2000
        ev = ThinkingEvent(text=long_text)
        html_out = thinking_detail_html(ev)
        # The inner text should be at most 1500 chars (before HTML escaping)
        assert "<blockquote>" in html_out
        assert "Thinking" in html_out
        # The raw 'A' count inside the blockquote should be <= 1500
        import re
        bq_match = re.search(r"<blockquote>(.*?)</blockquote>", html_out, re.DOTALL)
        assert bq_match is not None
        assert len(bq_match.group(1)) <= 1500

    def test_thinking_line_limit(self):
        """Thinking text with more than 15 lines is truncated to 15 lines."""
        lines = [f"Line {i}" for i in range(30)]
        ev = ThinkingEvent(text="\n".join(lines))
        html_out = thinking_detail_html(ev)
        import re
        bq_match = re.search(r"<blockquote>(.*?)</blockquote>", html_out, re.DOTALL)
        assert bq_match is not None
        inner_lines = bq_match.group(1).split("\n")
        assert len(inner_lines) <= 15


class TestToolIcon:
    def test_known_tool(self):
        """Known tool name returns its specific icon."""
        assert _tool_icon("Read", False) == "\U0001f4d6"  # book

    def test_unknown_tool(self):
        """Unknown tool name returns the default wrench icon."""
        assert _tool_icon("CustomTool", False) == "\U0001f527"  # wrench

    def test_error_tool(self):
        """Any tool with is_error=True returns the error icon."""
        assert _tool_icon("Read", True) == "\u274c"  # cross mark
        assert _tool_icon("CustomTool", True) == "\u274c"
