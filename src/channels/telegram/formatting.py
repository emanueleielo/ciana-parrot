"""Telegram formatting utilities shared between channel and handlers."""

import html
import re

TELEGRAM_MAX_MESSAGE_LEN = 4096


def md_to_telegram_html(text: str) -> str:
    """Convert Markdown to Telegram-compatible HTML."""
    # Pre-process: convert Markdown tables to fenced code blocks (monospace)
    text = _md_tables_to_monospace(text)

    # Split out fenced code blocks to protect them from further processing
    # Require closing ``` on its own line to avoid false matches
    # when tool results contain ``` mid-line
    parts = re.split(r"(```\w*\n[\s\S]*?\n```)", text)
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            # Fenced code block
            m = re.match(r"```(\w*)\n([\s\S]*?)\n```", part)
            if m:
                lang, code = m.group(1), m.group(2).rstrip()
                escaped = html.escape(code)
                if lang:
                    result.append(f'<pre><code class="language-{lang}">{escaped}</code></pre>')
                else:
                    result.append(f"<pre>{escaped}</pre>")
            else:
                result.append(html.escape(part))
        else:
            result.append(_md_inline_to_html(part))
    return "".join(result)


def _md_inline_to_html(text: str) -> str:
    """Convert inline Markdown to Telegram HTML."""
    # Protect inline code spans first
    codes: list[str] = []

    def _save_code(m: re.Match) -> str:
        codes.append(html.escape(m.group(1)))
        return f"\x00CODE{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", _save_code, text)

    # Escape HTML in the rest
    text = html.escape(text)

    # Bold: **text** or __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    # Italic: *text* or _text_  (but not inside words like file_name)
    text = re.sub(r"(?<!\w)\*([^*]+?)\*(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_([^_]+?)_(?!\w)", r"<i>\1</i>", text)
    # Strikethrough: ~~text~~
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)
    # Links: [text](url)
    text = re.sub(r"\[([^\]]+)]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    # Headers: # text → bold
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    # Blockquotes: > text
    text = re.sub(
        r"^(?:&gt;|>) (.+)$", r"<blockquote>\1</blockquote>", text, flags=re.MULTILINE
    )
    # Merge adjacent blockquotes
    text = re.sub(r"</blockquote>\n<blockquote>", "\n", text)
    # Horizontal rules: --- or *** → line
    text = re.sub(r"^[-*]{3,}$", "—" * 20, text, flags=re.MULTILINE)

    # Restore inline code
    for idx, code in enumerate(codes):
        text = text.replace(f"\x00CODE{idx}\x00", f"<code>{code}</code>")

    return text


def strip_html_tags(text: str) -> str:
    """Remove HTML tags and unescape entities for plain-text fallback."""
    cleaned = re.sub(r"<[^>]+>", "", text)
    return html.unescape(cleaned)


def _could_be_table_row(line: str) -> bool:
    """Check if a line could be part of a Markdown table."""
    stripped = line.strip()
    if not stripped:
        return False
    return stripped.startswith('|') or stripped.count('|') >= 2


def _is_table_separator(line: str) -> bool:
    """Check if a line is a Markdown table separator (e.g., |---|---|)."""
    stripped = line.strip()
    if stripped.startswith('|'):
        stripped = stripped[1:]
    if stripped.endswith('|'):
        stripped = stripped[:-1]
    return bool(stripped) and bool(re.match(r'^[\s\-:|]+$', stripped)) and '-' in stripped


def _parse_table_cells(line: str) -> list[str]:
    """Parse a Markdown table row into a list of cell contents."""
    stripped = line.strip()
    if stripped.startswith('|'):
        stripped = stripped[1:]
    if stripped.endswith('|'):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split('|')]


def _format_table_block(table_lines: list[str]) -> str:
    """Format Markdown table lines as aligned monospace text."""
    rows = []
    for line in table_lines:
        if _is_table_separator(line):
            continue
        rows.append(_parse_table_cells(line))

    if not rows:
        return '\n'.join(table_lines)

    num_cols = max(len(row) for row in rows)
    col_widths = [0] * num_cols
    for row in rows:
        for j in range(min(len(row), num_cols)):
            col_widths[j] = max(col_widths[j], len(row[j]))

    output = []
    for idx, row in enumerate(rows):
        cells = []
        for j in range(num_cols):
            cell = row[j] if j < len(row) else ''
            cells.append(cell.ljust(col_widths[j]))
        output.append('  '.join(cells).rstrip())
        if idx == 0:
            output.append('  '.join('\u2500' * w for w in col_widths))

    return '\n'.join(output)


def _md_tables_to_monospace(text: str) -> str:
    """Convert Markdown tables to fenced code blocks for monospace rendering."""
    lines = text.split('\n')
    result = []
    i = 0
    in_code_block = False

    while i < len(lines):
        line = lines[i]

        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            result.append(line)
            i += 1
            continue

        if in_code_block:
            result.append(line)
            i += 1
            continue

        if _could_be_table_row(line):
            table_lines = []
            j = i
            while j < len(lines) and _could_be_table_row(lines[j]):
                table_lines.append(lines[j])
                j += 1

            if len(table_lines) >= 3 and _is_table_separator(table_lines[1]):
                formatted = _format_table_block(table_lines)
                result.append('```')
                result.append(formatted)
                result.append('```')
                i = j
            else:
                result.append(line)
                i += 1
        else:
            result.append(line)
            i += 1

    return '\n'.join(result)


def split_text(text: str, max_len: int) -> list[str]:
    """Split text into chunks respecting max length."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # Try to split at newline
        idx = text.rfind("\n", 0, max_len)
        if idx == -1:
            idx = max_len
        chunks.append(text[:idx])
        text = text[idx:].lstrip("\n")
    return chunks
