"""Shared rendering for agent responses — used by both normal and CC modes."""

import html

from ...events import TextEvent, ThinkingEvent, ToolCallEvent
from ...utils import truncate_text


def tool_detail_html(ev: ToolCallEvent) -> str:
    """Render a single tool call as Telegram HTML for the details view."""
    icon = "\u274c" if ev.is_error else "\u2022"
    name_esc = html.escape(ev.name)
    summary_esc = f" {html.escape(ev.input_summary)}" if ev.input_summary else ""
    header = f"{icon} <b>{name_esc}</b>{summary_esc}"
    if ev.result_text:
        truncated = truncate_text(ev.result_text, max_chars=2500, max_lines=25)
        return f"{header}\n<pre>{html.escape(truncated)}</pre>"
    return f"{header} \u2714"


def thinking_detail_html(ev: ThinkingEvent) -> str:
    """Render a thinking block as Telegram HTML for the details view."""
    lines = ev.text.splitlines()[:15]
    truncated = "\n".join(lines)
    if len(truncated) > 1500:
        truncated = truncated[:1500]
    return f"\U0001f4ad <b>Thinking</b>\n<blockquote>{html.escape(truncated)}</blockquote>"


def render_events(events: list, error: str = "") -> tuple[str, list[str]]:
    """Render a list of events into (compact_text, tool_detail_items).

    compact_text: main message with tool one-liners, thinking, and text.
    tool_detail_items: list of pre-formatted HTML strings, one per event.
    """
    if error:
        if "\n" in error:
            return f"Error:\n```\n{error}\n```", []
        return f"Error: {error}", []

    parts: list[str] = []
    tool_lines: list[str] = []

    def flush_tools():
        if tool_lines:
            parts.append("\n".join(tool_lines))
            tool_lines.clear()

    for ev in events:
        if isinstance(ev, ThinkingEvent):
            flush_tools()
            quoted = "\n".join(f"> {l}" for l in ev.text.splitlines()[:15])
            parts.append(f"**Thinking**\n{quoted}")

        elif isinstance(ev, ToolCallEvent):
            summary_str = f" {ev.input_summary}" if ev.input_summary else ""
            if ev.is_error and ev.result_text:
                icon = "\u274c"
                line = f"{icon} **{ev.name}**{summary_str}"
                truncated = truncate_text(ev.result_text, max_lines=8)
                flush_tools()
                parts.append(f"{line}\n```\n{truncated}\n```")
            else:
                icon = "\u274c" if ev.is_error else "\u2022"
                line = f"{icon} **{ev.name}**{summary_str}"
                tool_lines.append(line)

        elif isinstance(ev, TextEvent):
            flush_tools()
            parts.append(ev.text)

    flush_tools()

    # Build per-event HTML details (one message per tool/thinking)
    detail_items: list[str] = []
    for ev in events:
        if isinstance(ev, ToolCallEvent):
            detail_items.append(tool_detail_html(ev))
        elif isinstance(ev, ThinkingEvent):
            detail_items.append(thinking_detail_html(ev))

    compact = "\n\n".join(parts) if parts else "(empty response)"
    return compact, detail_items
