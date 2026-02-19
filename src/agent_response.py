"""Structured agent response and extraction helpers."""

from dataclasses import dataclass, field


@dataclass
class AgentResponse:
    """Structured response from the LangGraph agent."""
    text: str
    tool_calls: list[dict] = field(default_factory=list)


def extract_agent_response(result: dict) -> AgentResponse:
    """Extract structured response from a LangGraph agent result.

    Args:
        result: Raw dict from agent.ainvoke(), containing "messages" key.

    Returns:
        AgentResponse with text and tool_calls extracted.
    """
    messages = result.get("messages", [])
    if not messages:
        return AgentResponse(text="")

    content = messages[-1].content
    if isinstance(content, list):
        text = " ".join(
            block.get("text", "") for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    else:
        text = content

    tool_calls = []
    for msg in messages:
        if not hasattr(msg, "tool_calls"):
            continue
        for tc in msg.tool_calls:
            tool_calls.append({
                "name": tc.get("name", "unknown"),
                "args": tc.get("args", {}),
            })

    return AgentResponse(text=text, tool_calls=tool_calls)
