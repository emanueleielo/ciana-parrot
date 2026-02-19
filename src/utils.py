"""Shared utility functions."""

# Default limits for tool result truncation
TOOL_RESULT_MAX_LINES = 80
TOOL_RESULT_MAX_CHARS = 12000


def truncate_text(text: str,
                  max_chars: int = TOOL_RESULT_MAX_CHARS,
                  max_lines: int = TOOL_RESULT_MAX_LINES) -> str:
    """Truncate text by line count and character count, with context."""
    total_lines = text.count("\n") + 1
    total_chars = len(text)
    lines = text.splitlines()
    truncated = False

    if len(lines) > max_lines:
        lines = lines[:max_lines]
        truncated = True

    result = "\n".join(lines)
    if len(result) > max_chars:
        cut = result.rfind("\n", 0, max_chars)
        if cut == -1:
            cut = max_chars
        result = result[:cut]
        truncated = True

    if truncated:
        omitted_lines = total_lines - result.count("\n") - 1
        omitted_chars = total_chars - len(result)
        result = (result.rstrip()
                  + f"\n... ({omitted_lines} more lines, "
                    f"{omitted_chars} more chars omitted)")
    return result
