"""Structured agent response and extraction helpers."""

from dataclasses import dataclass, field

from .events import (
    TextEvent,
    ThinkingEvent,
    ToolCallEvent,
    extract_tool_result_text,
    summarize_tool_input,
)


@dataclass
class AgentResponse:
    """Structured response from the LangGraph agent."""
    text: str
    events: list = field(default_factory=list)


def extract_agent_response(result: dict) -> AgentResponse:
    """Extract structured response from a LangGraph agent result.

    Extracts tool calls paired with their results, thinking blocks,
    and text blocks from the message history (current turn only).

    Args:
        result: Raw dict from agent.ainvoke(), containing "messages" key.

    Returns:
        AgentResponse with text and events extracted.
    """
    messages = result.get("messages", [])
    if not messages:
        return AgentResponse(text="")

    # Scope to current turn: only messages after the last human message
    last_human_idx = -1
    for i, msg in enumerate(messages):
        if getattr(msg, "type", None) == "human":
            last_human_idx = i

    turn_messages = messages[last_human_idx + 1:] if last_human_idx >= 0 else messages

    # First pass: collect tool results by tool_call_id
    tool_results: dict[str, tuple[str, bool]] = {}
    for msg in turn_messages:
        if getattr(msg, "type", None) == "tool":
            tc_id = getattr(msg, "tool_call_id", "")
            content_text = extract_tool_result_text(msg.content)
            is_error = getattr(msg, "status", "") == "error"
            tool_results[tc_id] = (content_text, is_error)

    # Second pass: build events from AI messages
    events: list = []
    for msg in turn_messages:
        if getattr(msg, "type", None) != "ai":
            continue

        content = msg.content
        has_tool_calls = bool(getattr(msg, "tool_calls", None))

        # Extract text/thinking from content
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and block.get("text", "").strip():
                    events.append(TextEvent(text=block["text"].strip()))
                elif block.get("type") == "thinking":
                    thinking = block.get("thinking", "")
                    if thinking.strip():
                        events.append(ThinkingEvent(text=thinking))
        elif isinstance(content, str) and content.strip() and not has_tool_calls:
            events.append(TextEvent(text=content.strip()))

        # Extract tool calls paired with results
        if has_tool_calls:
            for tc in msg.tool_calls:
                tc_id = tc.get("id", "")
                name = tc.get("name", "unknown")
                args = tc.get("args", {})
                result_text, is_error = tool_results.get(tc_id, ("", False))
                events.append(ToolCallEvent(
                    tool_id=tc_id,
                    name=name,
                    input_summary=summarize_tool_input(name, args),
                    result_text=result_text,
                    is_error=is_error,
                ))

    # Final text from last TextEvent
    final_text = ""
    for ev in reversed(events):
        if isinstance(ev, TextEvent):
            final_text = ev.text
            break

    return AgentResponse(text=final_text, events=events)
