"""Shared rendering for agent responses — used by both normal and CC modes."""

import html
from itertools import groupby

from ...events import TextEvent, ThinkingEvent, ToolCallEvent
from ...utils import truncate_text

# Tool name → emoji for compact display
_TOOL_ICONS: dict[str, str] = {
    # CC / DeepAgents PascalCase
    "Read": "\U0001f4d6",         # 📖
    "NotebookRead": "\U0001f4d6", # 📖
    "Write": "\u270f\ufe0f",      # ✏️
    "Edit": "\u270f\ufe0f",       # ✏️
    "NotebookEdit": "\u270f\ufe0f",
    "Bash": "\u26a1",             # ⚡
    "Grep": "\U0001f50d",         # 🔍
    "Glob": "\U0001f50d",         # 🔍
    "Task": "\U0001f916",         # 🤖
    "WebSearch": "\U0001f310",    # 🌐
    "WebFetch": "\U0001f310",     # 🌐
    # DeepAgents snake_case variants
    "read_file": "\U0001f4d6",    # 📖
    "write_file": "\u270f\ufe0f", # ✏️
    "edit_file": "\u270f\ufe0f",  # ✏️
    "ls": "\U0001f4c2",           # 📂
    "glob": "\U0001f50d",         # 🔍
    "grep": "\U0001f50d",         # 🔍
    # Custom Ciana tools
    "web_search": "\U0001f310",   # 🌐
    "web_fetch": "\U0001f310",    # 🌐
    "schedule_task": "\u23f0",    # ⏰
    "list_tasks": "\U0001f4cb",   # 📋
    "cancel_task": "\U0001f6ab",  # 🚫
}
_DEFAULT_ICON = "\U0001f527"  # 🔧


def _tool_icon(name: str, is_error: bool) -> str:
    """Return the emoji for a tool, or ❌ on error."""
    if is_error:
        return "\u274c"
    return _TOOL_ICONS.get(name, _DEFAULT_ICON)


def tool_detail_html(ev: ToolCallEvent) -> str:
    """Render a single tool call as Telegram HTML for the details view."""
    icon = _tool_icon(ev.name, ev.is_error)
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


def _build_compact_lines(events: list) -> list[str]:
    """Build compact lines from events, grouping and collapsing sub-agents.

    - Consecutive same-name tools are grouped: "📖 Read 2 files"
    - Sub-agent (Task) events are collapsed: only the Task title shows,
      all intermediate tool calls/text/thinking until the final answer are hidden.
    """
    # Identify sub-agent regions: indices to skip in compact view.
    # After a Task tool call, skip all events until the last TextEvent.
    skip: set[int] = set()
    i = 0
    while i < len(events):
        ev = events[i]
        if isinstance(ev, ToolCallEvent) and ev.name == "Task":
            # Find the last TextEvent after this Task — that's the final answer.
            # Everything between the Task and that last TextEvent is sub-agent noise.
            last_text_idx = None
            for j in range(i + 1, len(events)):
                if isinstance(events[j], TextEvent):
                    last_text_idx = j
            if last_text_idx is not None:
                for j in range(i + 1, last_text_idx):
                    skip.add(j)
        i += 1

    # Build visible events (excluding skipped sub-agent internals)
    visible = [(idx, ev) for idx, ev in enumerate(events) if idx not in skip]

    parts: list[str] = []
    tool_lines: list[str] = []

    def flush_tools():
        if tool_lines:
            parts.append("\n".join(tool_lines))
            tool_lines.clear()

    # Group consecutive tool calls of the same name
    vi = 0
    while vi < len(visible):
        _, ev = visible[vi]

        if isinstance(ev, ThinkingEvent):
            tool_lines.append("\U0001f4ad Thinking\u2026")
            vi += 1

        elif isinstance(ev, ToolCallEvent):
            if ev.is_error and ev.result_text:
                icon = _tool_icon(ev.name, ev.is_error)
                summary_str = f" {ev.input_summary}" if ev.input_summary else ""
                line = f"{icon} **{ev.name}**{summary_str}"
                truncated = truncate_text(ev.result_text, max_lines=8)
                flush_tools()
                parts.append(f"{line}\n```\n{truncated}\n```")
                vi += 1
            elif ev.name == "Task":
                icon = _tool_icon(ev.name, False)
                summary_str = f" {ev.input_summary}" if ev.input_summary else ""
                tool_lines.append(f"{icon} **{ev.name}**{summary_str} \u2714")
                vi += 1
            else:
                # Count consecutive same-name non-error tool calls
                group_name = ev.name
                group_icon = _tool_icon(group_name, False)
                count = 0
                summaries: list[str] = []
                while vi < len(visible):
                    _, gev = visible[vi]
                    if (isinstance(gev, ToolCallEvent)
                            and gev.name == group_name
                            and not (gev.is_error and gev.result_text)):
                        count += 1
                        if gev.input_summary:
                            summaries.append(gev.input_summary)
                        vi += 1
                    else:
                        break

                if count == 1:
                    summary_str = f" {summaries[0]}" if summaries else ""
                    tool_lines.append(f"{group_icon} **{group_name}**{summary_str}")
                else:
                    tool_lines.append(
                        f"{group_icon} **{group_name}** {count} calls")

        elif isinstance(ev, TextEvent):
            flush_tools()
            parts.append(ev.text)
            vi += 1
        else:
            vi += 1

    flush_tools()
    return parts


def render_events(events: list, error: str = "") -> tuple[str, list[str]]:
    """Render a list of events into (compact_text, tool_detail_items).

    compact_text: main message with tool one-liners, thinking, and text.
    tool_detail_items: list of pre-formatted HTML strings, one per event.
    """
    if error:
        if "\n" in error:
            return f"Error:\n```\n{error}\n```", []
        return f"Error: {error}", []

    parts = _build_compact_lines(events)

    # Build per-event HTML details (one message per tool/thinking) — always full
    detail_items: list[str] = []
    for ev in events:
        if isinstance(ev, ToolCallEvent):
            detail_items.append(tool_detail_html(ev))
        elif isinstance(ev, ThinkingEvent):
            detail_items.append(thinking_detail_html(ev))

    compact = "\n\n".join(parts) if parts else "(empty response)"
    return compact, detail_items
