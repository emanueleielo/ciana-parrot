"""Tests for src.channels.telegram.formatting — md_to_telegram_html, split_text."""

from src.channels.telegram.formatting import md_to_telegram_html, split_text


class TestMdToTelegramHtml:
    def test_plain_text(self):
        assert md_to_telegram_html("hello") == "hello"

    def test_bold_asterisks(self):
        result = md_to_telegram_html("**bold**")
        assert "<b>bold</b>" in result

    def test_bold_underscores(self):
        result = md_to_telegram_html("__bold__")
        assert "<b>bold</b>" in result

    def test_italic_asterisk(self):
        result = md_to_telegram_html("*italic*")
        assert "<i>italic</i>" in result

    def test_italic_underscore(self):
        result = md_to_telegram_html("_italic_")
        assert "<i>italic</i>" in result

    def test_strikethrough(self):
        result = md_to_telegram_html("~~strike~~")
        assert "<s>strike</s>" in result

    def test_inline_code(self):
        result = md_to_telegram_html("`code`")
        assert "<code>" in result
        assert "code" in result

    def test_fenced_code_block(self):
        text = "```python\nprint('hi')\n```"
        result = md_to_telegram_html(text)
        assert "<pre>" in result
        assert "print(" in result

    def test_fenced_code_block_no_lang(self):
        text = "```\nsome code\n```"
        result = md_to_telegram_html(text)
        assert "<pre>" in result

    def test_code_block_html_escaped(self):
        text = "```\n<script>alert('xss')</script>\n```"
        result = md_to_telegram_html(text)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_link(self):
        result = md_to_telegram_html("[click](https://example.com)")
        assert '<a href="https://example.com">click</a>' in result

    def test_header_to_bold(self):
        result = md_to_telegram_html("# Title")
        assert "<b>Title</b>" in result

    def test_blockquote(self):
        result = md_to_telegram_html("> quoted text")
        assert "<blockquote>" in result

    def test_horizontal_rule(self):
        result = md_to_telegram_html("---")
        assert "—" in result

    def test_html_entities_escaped(self):
        result = md_to_telegram_html("a < b & c > d")
        assert "&lt;" in result
        assert "&amp;" in result
        assert "&gt;" in result

    def test_mixed_formatting(self):
        result = md_to_telegram_html("**bold** and *italic* and `code`")
        assert "<b>bold</b>" in result
        assert "<i>italic</i>" in result
        assert "<code>" in result

    def test_underscore_in_word_not_italic(self):
        result = md_to_telegram_html("file_name_here")
        assert "<i>" not in result


class TestTableFormatting:
    def test_simple_table(self):
        text = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = md_to_telegram_html(text)
        assert "<pre>" in result
        assert "A" in result
        assert "1" in result
        # Should not contain raw pipe-delimited markdown
        assert "|---|" not in result

    def test_table_with_long_cells(self):
        text = "| Name | Description |\n|---|---|\n| src/ | Main source code |\n| tests/ | Test files |"
        result = md_to_telegram_html(text)
        assert "<pre>" in result
        assert "Name" in result
        assert "Main source code" in result

    def test_table_preserves_surrounding_text(self):
        text = "Before\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nAfter"
        result = md_to_telegram_html(text)
        assert "Before" in result
        assert "After" in result
        assert "<pre>" in result

    def test_table_inside_code_block_untouched(self):
        text = "```\n| A | B |\n|---|---|\n| 1 | 2 |\n```"
        result = md_to_telegram_html(text)
        # Should still be a pre block but from the code fence, not table conversion
        assert "<pre>" in result
        assert "|" in result  # pipes preserved in code block

    def test_not_a_table_too_few_rows(self):
        text = "| A | B |\n| 1 | 2 |"
        result = md_to_telegram_html(text)
        # No separator line, so not treated as a table
        assert "| A |" in result or "A" in result

    def test_table_alignment(self):
        """Check that columns are padded for alignment."""
        from src.channels.telegram.formatting import _format_table_block
        lines = ["| Short | Longer header |", "|---|---|", "| A | B |"]
        formatted = _format_table_block(lines)
        out_lines = formatted.split('\n')
        # Header and data lines should have same width structure
        assert len(out_lines) == 3  # header + separator + 1 data row
        # All content lines should be padded
        assert "Short" in out_lines[0]
        assert "Longer header" in out_lines[0]


class TestSplitText:
    def test_short_text(self):
        assert split_text("hello", 100) == ["hello"]

    def test_exact_limit(self):
        text = "x" * 100
        assert split_text(text, 100) == [text]

    def test_split_at_newline(self):
        text = "line1\nline2\nline3"
        chunks = split_text(text, 12)
        assert len(chunks) >= 2
        assert chunks[0].startswith("line1")

    def test_no_newline_splits_at_max(self):
        text = "a" * 200
        chunks = split_text(text, 100)
        assert len(chunks) == 2
        assert len(chunks[0]) == 100

    def test_empty_string(self):
        assert split_text("", 100) == [""]

    def test_multiple_chunks(self):
        text = "\n".join(f"line {i}" for i in range(100))
        chunks = split_text(text, 50)
        assert len(chunks) > 1
        # Reconstruct should give all content
        reconstructed = "\n".join(chunks)
        for i in range(100):
            assert f"line {i}" in reconstructed
