"""Tests for Claude Code bridge — NDJSON parsing, _summarize_tool_input, _extract_tool_result_text."""

import json

import pytest

from src.bridges.claude_code.bridge import (
    ClaudeCodeBridge,
    CCResponse,
    TextEvent,
    ToolCallEvent,
    ThinkingEvent,
)
from src.config import AppConfig, ClaudeCodeConfig


@pytest.fixture
def bridge(tmp_path) -> ClaudeCodeBridge:
    config = AppConfig(
        claude_code=ClaudeCodeConfig(
            state_file=str(tmp_path / "cc_states.json"),
            projects_dir=str(tmp_path / "projects"),
        ),
    )
    return ClaudeCodeBridge(config)


class TestSummarizeToolInput:
    def test_read_file(self):
        result = ClaudeCodeBridge._summarize_tool_input(
            "Read", {"file_path": "/src/main.py"}
        )
        assert result == "main.py"

    def test_edit_file(self):
        result = ClaudeCodeBridge._summarize_tool_input(
            "Edit", {"file_path": "/path/to/file.txt"}
        )
        assert result == "file.txt"

    def test_glob_pattern(self):
        result = ClaudeCodeBridge._summarize_tool_input(
            "Glob", {"pattern": "**/*.py"}
        )
        assert result == "**/*.py"

    def test_bash_command(self):
        result = ClaudeCodeBridge._summarize_tool_input(
            "Bash", {"command": "git status"}
        )
        assert result == "git status"

    def test_bash_long_command(self):
        cmd = "x" * 100
        result = ClaudeCodeBridge._summarize_tool_input(
            "Bash", {"command": cmd}
        )
        assert result.endswith("...")
        assert len(result) <= 74  # 70 + "..."

    def test_fallback_known_keys(self):
        result = ClaudeCodeBridge._summarize_tool_input(
            "CustomTool", {"query": "search term"}
        )
        assert result == "search term"

    def test_fallback_any_string_value(self):
        result = ClaudeCodeBridge._summarize_tool_input(
            "CustomTool", {"data": "some value"}
        )
        assert result == "some value"

    def test_empty_input(self):
        result = ClaudeCodeBridge._summarize_tool_input("Tool", {})
        assert result == ""

    def test_empty_file_path(self):
        result = ClaudeCodeBridge._summarize_tool_input("Read", {"file_path": ""})
        assert result == ""


class TestExtractToolResultText:
    def test_none(self):
        assert ClaudeCodeBridge._extract_tool_result_text(None) == ""

    def test_string(self):
        assert ClaudeCodeBridge._extract_tool_result_text("  hello  ") == "hello"

    def test_list_text_blocks(self):
        content = [
            {"type": "text", "text": "line 1"},
            {"type": "text", "text": "line 2"},
        ]
        result = ClaudeCodeBridge._extract_tool_result_text(content)
        assert "line 1" in result
        assert "line 2" in result

    def test_list_with_image(self):
        content = [
            {"type": "text", "text": "before"},
            {"type": "image"},
            {"type": "text", "text": "after"},
        ]
        result = ClaudeCodeBridge._extract_tool_result_text(content)
        assert "[image]" in result
        assert "before" in result

    def test_list_strings(self):
        content = ["plain string"]
        result = ClaudeCodeBridge._extract_tool_result_text(content)
        assert result == "plain string"

    def test_dict_text_type(self):
        content = {"type": "text", "text": "  result  "}
        result = ClaudeCodeBridge._extract_tool_result_text(content)
        assert result == "result"

    def test_dict_other_type(self):
        content = {"type": "data", "value": 42}
        result = ClaudeCodeBridge._extract_tool_result_text(content)
        assert "42" in result

    def test_other_type(self):
        assert ClaudeCodeBridge._extract_tool_result_text(42) == "42"


class TestParseNdjsonResponse:
    def test_empty_string(self, bridge):
        resp = bridge._parse_cc_json_response("")
        assert len(resp.events) == 1
        assert isinstance(resp.events[0], TextEvent)

    def test_single_result_json(self, bridge):
        data = json.dumps({"type": "result", "result": "Final answer"})
        resp = bridge._parse_cc_json_response(data)
        assert len(resp.events) == 1
        assert resp.events[0].text == "Final answer"

    def test_single_content_blocks(self, bridge):
        data = json.dumps({
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "tool_use", "id": "t1", "name": "Read",
                 "input": {"file_path": "/a/b.py"}},
            ]
        })
        resp = bridge._parse_cc_json_response(data)
        texts = [e for e in resp.events if isinstance(e, TextEvent)]
        tools = [e for e in resp.events if isinstance(e, ToolCallEvent)]
        assert len(texts) == 1
        assert len(tools) == 1
        assert tools[0].name == "Read"

    def test_ndjson_stream(self, bridge):
        lines = [
            json.dumps({
                "type": "assistant",
                "content": [{"type": "text", "text": "thinking..."}],
            }),
            json.dumps({
                "type": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "Bash",
                     "input": {"command": "ls"}},
                ],
            }),
            json.dumps({
                "type": "assistant",
                "content": [
                    {"type": "tool_result", "tool_use_id": "t1",
                     "is_error": False, "content": "file.txt"},
                ],
            }),
            json.dumps({
                "type": "assistant",
                "content": [{"type": "text", "text": "Done!"}],
            }),
            json.dumps({"type": "result", "result": "Final"}),
        ]
        raw = "\n".join(lines)
        resp = bridge._parse_cc_json_response(raw)
        assert resp.error == ""
        texts = [e for e in resp.events if isinstance(e, TextEvent)]
        tools = [e for e in resp.events if isinstance(e, ToolCallEvent)]
        assert len(texts) >= 1
        assert any("Done" in t.text for t in texts)
        assert len(tools) == 1
        assert tools[0].name == "Bash"
        assert tools[0].result_text == "file.txt"

    def test_ndjson_with_thinking(self, bridge):
        lines = [
            json.dumps({
                "type": "assistant",
                "content": [{"type": "thinking", "thinking": "Let me think..."}],
            }),
            json.dumps({
                "type": "assistant",
                "content": [{"type": "text", "text": "Answer"}],
            }),
        ]
        raw = "\n".join(lines)
        resp = bridge._parse_cc_json_response(raw)
        thinking = [e for e in resp.events if isinstance(e, ThinkingEvent)]
        assert len(thinking) == 1
        assert "think" in thinking[0].text.lower()

    def test_ndjson_error_tool_result(self, bridge):
        lines = [
            json.dumps({
                "type": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "Bash",
                     "input": {"command": "false"}},
                ],
            }),
            json.dumps({
                "type": "assistant",
                "content": [
                    {"type": "tool_result", "tool_use_id": "t1",
                     "is_error": True, "content": "command failed"},
                ],
            }),
        ]
        raw = "\n".join(lines)
        resp = bridge._parse_cc_json_response(raw)
        tools = [e for e in resp.events if isinstance(e, ToolCallEvent)]
        assert len(tools) == 1
        assert tools[0].is_error is True
        assert "failed" in tools[0].result_text

    def test_non_json_lines_ignored(self, bridge):
        raw = "not json\n" + json.dumps({"type": "result", "result": "ok"})
        resp = bridge._parse_cc_json_response(raw)
        # Single parseable line → single-JSON path
        assert any(isinstance(e, TextEvent) for e in resp.events)

    def test_plain_text_fallback(self, bridge):
        raw = "Just plain text output"
        resp = bridge._parse_cc_json_response(raw)
        assert resp.error == raw
