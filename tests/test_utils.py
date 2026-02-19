"""Tests for src.utils — truncate_text."""

from src.utils import truncate_text, TOOL_RESULT_MAX_CHARS, TOOL_RESULT_MAX_LINES


class TestTruncateText:
    def test_short_text_unchanged(self):
        text = "hello world"
        assert truncate_text(text) == text

    def test_empty_string(self):
        assert truncate_text("") == ""

    def test_single_line_within_limits(self):
        text = "a" * 100
        assert truncate_text(text) == text

    def test_truncate_by_lines(self):
        lines = [f"line {i}" for i in range(200)]
        text = "\n".join(lines)
        result = truncate_text(text, max_lines=10, max_chars=100_000)
        assert "line 0" in result
        assert "line 9" in result
        assert "more lines" in result

    def test_truncate_by_chars(self):
        text = "a" * 50000
        result = truncate_text(text, max_chars=100, max_lines=10000)
        assert len(result) < 50000
        assert "more chars omitted" in result

    def test_truncate_by_both(self):
        lines = ["x" * 100 for _ in range(200)]
        text = "\n".join(lines)
        result = truncate_text(text, max_chars=500, max_lines=3)
        assert "more lines" in result or "more chars" in result

    def test_exact_line_limit(self):
        lines = [f"line {i}" for i in range(TOOL_RESULT_MAX_LINES)]
        text = "\n".join(lines)
        result = truncate_text(text)
        # Exactly at limit — should not be truncated
        assert "omitted" not in result

    def test_one_over_line_limit(self):
        lines = [f"line {i}" for i in range(TOOL_RESULT_MAX_LINES + 1)]
        text = "\n".join(lines)
        result = truncate_text(text)
        assert "omitted" in result

    def test_preserves_newline_boundary(self):
        text = "short\n" + "x" * 200
        result = truncate_text(text, max_chars=50, max_lines=1000)
        # Should cut at a newline boundary when possible
        assert "omitted" in result

    def test_custom_limits(self):
        text = "line1\nline2\nline3\nline4"
        result = truncate_text(text, max_chars=100_000, max_lines=2)
        assert "line1" in result
        assert "line2" in result
        assert "more lines" in result
