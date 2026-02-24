"""Shared event types for agent responses (used by both normal and CC modes)."""

import json
from dataclasses import dataclass, field

from .utils import TOOL_RESULT_MAX_CHARS


# --- Event types ---

@dataclass
class ToolCallEvent:
    """A single tool invocation with its result."""
    tool_id: str
    name: str
    input_summary: str
    result_text: str
    is_error: bool
    display_name: str = ""  # human-friendly label (e.g., "Spotify", "Web Search")


@dataclass
class ThinkingEvent:
    """An extended-thinking block."""
    text: str


@dataclass
class TextEvent:
    """A plain text block from the assistant."""
    text: str


# --- Helper functions ---

def summarize_tool_input(tool_name: str, input_data: dict) -> str:
    """Create a compact one-line summary of tool input for display."""
    if tool_name in ("Read", "Write", "NotebookEdit", "Edit",
                      "read_file", "write_file", "edit_file"):
        fp = input_data.get("file_path") or input_data.get("path", "")
        return fp.rsplit("/", 1)[-1] if fp else ""
    if tool_name in ("Glob", "Grep", "glob", "grep"):
        return input_data.get("pattern", "")[:60]
    if tool_name == "Bash":
        cmd = input_data.get("command", "")
        return cmd[:70] + "..." if len(cmd) > 70 else cmd
    if tool_name == "host_execute":
        cmd = input_data.get("command", "")
        return cmd[:70] + "..." if len(cmd) > 70 else cmd

    # Generic fallback: try common keys, then any string value
    for key in ("file_path", "command", "pattern", "query", "url"):
        if key in input_data and isinstance(input_data[key], str):
            val = input_data[key]
            return val[:70] + "..." if len(val) > 70 else val
    for v in input_data.values():
        if isinstance(v, str) and v:
            return v[:60] + "..." if len(v) > 60 else v
    return ""


# Display name mapping for snake_case / internal tools
_TOOL_DISPLAY_NAMES: dict[str, str] = {
    "web_search": "Web Search",
    "web_fetch": "Web Fetch",
    "schedule_task": "Schedule",
    "list_tasks": "Tasks",
    "cancel_task": "Cancel Task",
    "read_file": "Read",
    "write_file": "Write",
    "edit_file": "Edit",
    "NotebookRead": "Read",
    "NotebookEdit": "Edit",
}


def resolve_display_name(tool_name: str, args: dict) -> str:
    """Resolve a human-friendly display name for a tool call.

    For host_execute, returns the bridge name as a label (e.g., "Spotify").
    For other tools, returns a friendly label or empty string to use the raw name.
    """
    if tool_name == "host_execute":
        bridge = args.get("bridge", "")
        return bridge.replace("-", " ").title() if bridge else "Host"
    return _TOOL_DISPLAY_NAMES.get(tool_name, "")


def extract_tool_result_text(content) -> str:
    """Normalize tool result content (str, list, dict) into plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
                elif item.get("type") == "image":
                    texts.append("[image]")
                else:
                    texts.append(str(item))
            elif isinstance(item, str):
                texts.append(item)
        return "\n".join(texts).strip()
    if isinstance(content, dict):
        if content.get("type") == "text":
            return content.get("text", "").strip()
        return json.dumps(content, indent=2)[:TOOL_RESULT_MAX_CHARS]
    return str(content).strip()
