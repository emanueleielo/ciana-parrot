"""Workspace shell backend — FilesystemBackend + allowlisted execute."""

from __future__ import annotations

import asyncio
import shlex
import subprocess
import uuid
from pathlib import PurePosixPath

from deepagents.backends import FilesystemBackend
from deepagents.backends.protocol import ExecuteResponse, SandboxBackendProtocol

# Commands allowed via execute. Everything else → use file tools.
ALLOWED_COMMANDS = frozenset({
    "curl", "wget",                     # HTTP
    "python", "python3", "pip", "pip3", # Python
    "git",                              # Version control
    "jq",                               # JSON processing
    "ffmpeg", "ffprobe",                # Media processing
    "nano-pdf",                         # PDF editing (Gemini-powered)
    "echo", "date", "whoami",            # Basic utils
    "tar", "gzip", "gunzip", "unzip",   # Archives
    "wc", "sort", "uniq", "tr", "cut",  # Text processing (on piped data)
    "base64", "sha256sum", "md5sum",    # Encoding/hashing
})


class WorkspaceShellBackend(SandboxBackendProtocol, FilesystemBackend):
    """FilesystemBackend with allowlisted shell execution.

    - File tools (ls, read_file, glob, grep) → sandboxed to workspace via virtual_mode
    - execute → only allows commands in ALLOWED_COMMANDS, runs in workspace dir
    """

    def __init__(self, *, root_dir, virtual_mode=True, timeout=120, max_output_bytes=100_000):
        super().__init__(root_dir=root_dir, virtual_mode=virtual_mode)
        self._timeout = timeout
        self._max_output = max_output_bytes
        self._sandbox_id = f"workspace-{uuid.uuid4().hex[:8]}"

    @property
    def id(self) -> str:
        return self._sandbox_id

    def execute(self, command: str) -> ExecuteResponse:
        if not command or not isinstance(command, str):
            return ExecuteResponse(output="Error: command must be a non-empty string.", exit_code=1)

        denied = _check_allowed(command)
        if denied:
            return ExecuteResponse(output=denied, exit_code=1)

        try:
            cmd_list = shlex.split(command)
        except ValueError:
            return ExecuteResponse(output="Error: malformed command.", exit_code=1)

        try:
            result = subprocess.run(
                cmd_list,
                shell=False,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=str(self.cwd),
            )
        except subprocess.TimeoutExpired:
            return ExecuteResponse(output=f"Error: timed out after {self._timeout}s.", exit_code=124)
        except Exception as e:
            return ExecuteResponse(output=f"Error: {e}", exit_code=1)
        return self._format(result)

    async def aexecute(self, command: str) -> ExecuteResponse:
        return await asyncio.to_thread(self.execute, command)

    def _format(self, result: subprocess.CompletedProcess) -> ExecuteResponse:
        parts = []
        if result.stdout:
            parts.append(result.stdout)
        if result.stderr:
            for line in result.stderr.strip().splitlines():
                parts.append(f"[stderr] {line}")
        output = "\n".join(parts) if parts else "<no output>"
        truncated = len(output) > self._max_output
        if truncated:
            output = output[:self._max_output] + "\n\n... truncated."
        if result.returncode != 0:
            output = f"{output.rstrip()}\n\nExit code: {result.returncode}"
        return ExecuteResponse(output=output, exit_code=result.returncode, truncated=truncated)


def _check_allowed(command: str) -> str | None:
    """Return error message if command is not allowed, None if OK.

    Safety relies on subprocess ``shell=False`` (list exec, no shell
    interpretation) + this command allowlist.  Metacharacters like ``&``
    inside arguments are harmless because no shell ever sees them.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return "Error: malformed command."
    if not tokens:
        return "Error: empty command."

    # First token is the command (possibly with path)
    cmd = PurePosixPath(tokens[0]).name
    if cmd not in ALLOWED_COMMANDS:
        return (
            f"Error: '{cmd}' is not allowed. "
            f"Use file tools (ls, read_file, glob, grep) for file operations. "
            f"Allowed commands: {', '.join(sorted(ALLOWED_COMMANDS))}"
        )
    return None
