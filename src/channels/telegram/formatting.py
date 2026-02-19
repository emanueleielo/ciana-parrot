"""Telegram formatting utilities shared between channel and handlers."""

import html
import re

TELEGRAM_MAX_MESSAGE_LEN = 4096


def md_to_telegram_html(text: str) -> str:
    """Convert Markdown to Telegram-compatible HTML."""
    # Split out fenced code blocks to protect them from further processing
    parts = re.split(r"(```[\s\S]*?```)", text)
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            # Fenced code block
            m = re.match(r"```(\w*)\n?([\s\S]*?)```", part)
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
