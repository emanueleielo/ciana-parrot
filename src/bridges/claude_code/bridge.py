"""Claude Code bridge - browse projects/conversations and run Claude Code from Telegram."""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from ...config import AppConfig
from ...store import JsonStore
from ...utils import TOOL_RESULT_MAX_CHARS

logger = logging.getLogger(__name__)


# --- Structured event types ---

@dataclass
class ToolCallEvent:
    """A single tool invocation with its result."""
    tool_id: str
    name: str
    input_summary: str
    result_text: str
    is_error: bool


@dataclass
class ThinkingEvent:
    """An extended-thinking block."""
    text: str


@dataclass
class TextEvent:
    """A plain text block from the assistant."""
    text: str


@dataclass
class CCResponse:
    """Parsed response from Claude Code CLI.

    Either contains structured events (normal response) or an error string.
    """
    events: list = field(default_factory=list)
    error: str = ""


# --- Domain types ---

@dataclass
class ConversationInfo:
    session_id: str
    first_message: str
    timestamp: datetime
    message_count: int
    git_branch: str = ""
    cwd: str = ""


@dataclass
class ProjectInfo:
    encoded_name: str
    real_path: str
    display_name: str
    conversation_count: int
    last_activity: Optional[datetime] = None


@dataclass
class UserSession:
    mode: str = "ciana"
    active_project: Optional[str] = None
    active_project_path: Optional[str] = None
    active_session_id: Optional[str] = None


class ClaudeCodeBridge:
    """Manages Claude Code CLI interactions, locally or via host bridge."""

    def __init__(self, config: AppConfig):
        cc = config.claude_code
        self._claude_path = cc.claude_path
        self._projects_dir = Path(os.path.expanduser(cc.projects_dir))
        self._timeout = cc.timeout
        self._permission_mode = cc.permission_mode
        self._bridge_url = cc.bridge_url
        self._bridge_token = cc.bridge_token
        self._store = JsonStore(cc.state_file)
        self._user_states: dict[str, UserSession] = {}
        self._restore_states()

    def get_user_state(self, user_id: str) -> UserSession:
        if user_id not in self._user_states:
            self._user_states[user_id] = UserSession()
        return self._user_states[user_id]

    def is_claude_code_mode(self, user_id: str) -> bool:
        state = self._user_states.get(user_id)
        return state is not None and state.mode == "claude_code"

    def exit_mode(self, user_id: str) -> None:
        if user_id in self._user_states:
            self._user_states[user_id] = UserSession()
        self._store.delete(user_id)

    def list_projects(self) -> list[ProjectInfo]:
        """Scan ~/.claude/projects/ and return project info sorted by most recent."""
        if not self._projects_dir.exists():
            return []

        projects = []
        for project_dir in self._projects_dir.iterdir():
            if not project_dir.is_dir():
                continue
            jsonl_files = sorted(project_dir.glob("*.jsonl"),
                                 key=lambda f: f.stat().st_mtime, reverse=True)
            if not jsonl_files:
                continue

            real_path = self._peek_cwd(jsonl_files[0])
            display_name = real_path.rsplit("/", 1)[-1] if real_path else project_dir.name
            last_activity = datetime.fromtimestamp(
                jsonl_files[0].stat().st_mtime, tz=timezone.utc
            )

            projects.append(ProjectInfo(
                encoded_name=project_dir.name,
                real_path=real_path or project_dir.name,
                display_name=display_name,
                conversation_count=len(jsonl_files),
                last_activity=last_activity,
            ))

        projects.sort(key=lambda p: p.last_activity or datetime.min.replace(tzinfo=timezone.utc),
                       reverse=True)
        return projects

    def list_conversations(self, project_encoded: str) -> list[ConversationInfo]:
        """Parse JSONL files for a project and return conversation metadata."""
        project_dir = self._projects_dir / project_encoded
        if not project_dir.exists():
            return []

        conversations = []
        for jsonl_file in project_dir.glob("*.jsonl"):
            info = self._parse_conversation(jsonl_file)
            if info:
                conversations.append(info)

        conversations.sort(key=lambda c: c.timestamp, reverse=True)
        return conversations

    def activate_session(self, user_id: str, project_encoded: str,
                         project_path: str, session_id: Optional[str] = None) -> None:
        """Set user into Claude Code mode for a specific project/session."""
        state = self.get_user_state(user_id)
        state.mode = "claude_code"
        state.active_project = project_encoded
        state.active_project_path = project_path
        state.active_session_id = session_id
        self._persist_user(user_id)

    async def send_message(self, user_id: str, text: str) -> CCResponse:
        """Send a message to Claude Code CLI and return the response."""
        state = self.get_user_state(user_id)
        cmd = self._build_command(text, state)
        cwd = state.active_project_path

        # Snapshot existing sessions before subprocess so we can detect the new one
        existing_sessions: set[str] = set()
        if not state.active_session_id and state.active_project:
            project_dir = self._projects_dir / state.active_project
            if project_dir.exists():
                existing_sessions = {f.stem for f in project_dir.glob("*.jsonl")}

        result = await self._execute_command(cmd, cwd)

        # If this was a new conversation, find the session that didn't exist before
        if not state.active_session_id and state.active_project:
            new_id = self._detect_new_session(state.active_project, existing_sessions)
            if new_id:
                state.active_session_id = new_id
                self._persist_user(user_id)
                logger.info("Detected new session: %s", new_id)

        return result

    async def check_available(self) -> tuple[bool, str]:
        """Check if Claude Code is accessible (via bridge or local CLI)."""
        if self._bridge_url:
            return await self._check_bridge()
        return await self._check_local()

    # --- Private helpers ---

    def _build_command(self, text: str, state: UserSession) -> list[str]:
        cmd = [self._claude_path, "-p"]
        if state.active_session_id:
            cmd.extend(["--resume", state.active_session_id])
        cmd.extend(["--output-format", "stream-json", "--verbose"])
        if self._permission_mode:
            cmd.extend(["--permission-mode", self._permission_mode])
        cmd.append(text)
        return cmd

    async def _execute_command(self, cmd: list[str], cwd: Optional[str] = None) -> CCResponse:
        if self._bridge_url:
            return await self._execute_via_bridge(cmd, cwd)
        return await self._execute_local(cmd, cwd)

    async def _execute_via_bridge(self, cmd: list[str], cwd: Optional[str] = None) -> CCResponse:
        headers = {}
        if self._bridge_token:
            headers["Authorization"] = f"Bearer {self._bridge_token}"

        http_timeout = httpx.Timeout(None) if self._timeout == 0 else self._timeout + 10

        try:
            async with httpx.AsyncClient(timeout=http_timeout) as client:
                resp = await client.post(
                    f"{self._bridge_url}/execute",
                    json={"cmd": cmd, "cwd": cwd, "timeout": self._timeout},
                    headers=headers,
                )
            if resp.status_code == 401:
                return CCResponse(error="Bridge auth failed. Check CC_BRIDGE_TOKEN.")
            data = resp.json()
        except httpx.ConnectError:
            return CCResponse(error="Cannot connect to Claude Code bridge. Is the bridge server running?")
        except httpx.TimeoutException:
            return CCResponse(error="Command timed out.")
        except Exception as e:
            logger.exception("Bridge request failed")
            return CCResponse(error=f"Bridge error: {e}")

        stdout = data.get("stdout", "").strip()
        stderr = data.get("stderr", "").strip()

        if data.get("returncode", 0) != 0:
            return CCResponse(error=stderr or "Claude Code returned an error.")

        if not stdout:
            if stderr:
                return CCResponse(error=stderr)
            return CCResponse(events=[TextEvent(text="(empty response)")])

        return self._parse_cc_json_response(stdout)

    async def _execute_local(self, cmd: list[str], cwd: Optional[str] = None) -> CCResponse:
        env = os.environ.copy()
        env.pop("CLAUDE_CODE", None)
        env.pop("CLAUDECODE", None)
        effective_cwd = cwd if cwd and Path(cwd).is_dir() else None

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=effective_cwd,
            )
            if self._timeout == 0:
                stdout, stderr = await proc.communicate()
            else:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self._timeout
                )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return CCResponse(error="Command timed out. The request may have been too complex.")
        except Exception as e:
            logger.exception("Error executing Claude Code command")
            return CCResponse(error=f"Error running Claude Code: {e}")

        out = stdout.decode().strip()
        err = stderr.decode().strip()

        if proc.returncode != 0:
            logger.warning("Claude Code exited %d: %s", proc.returncode, err)
            return CCResponse(error=err or "Claude Code returned an error.")

        if not out:
            if err:
                return CCResponse(error=err)
            return CCResponse(events=[TextEvent(text="(empty response)")])

        return self._parse_cc_json_response(out)

    async def _check_bridge(self) -> tuple[bool, str]:
        headers = {}
        if self._bridge_token:
            headers["Authorization"] = f"Bearer {self._bridge_token}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self._bridge_url}/health", headers=headers)
            if resp.status_code == 200:
                version = resp.json().get("claude", "unknown")
                return True, f"Bridge OK — {version}"
            return False, f"Bridge returned {resp.status_code}"
        except httpx.ConnectError:
            return False, "Cannot connect to Claude Code bridge"
        except Exception as e:
            return False, str(e)

    async def _check_local(self) -> tuple[bool, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                self._claude_path, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
            if proc.returncode == 0:
                return True, stdout.decode().strip()
            return False, stderr.decode().strip()
        except FileNotFoundError:
            return False, "claude CLI not found in PATH"
        except Exception as e:
            return False, str(e)

    def _parse_cc_json_response(self, raw: str) -> CCResponse:
        """Parse Claude Code stream-json (NDJSON) output into structured events."""
        if not raw:
            return CCResponse(events=[TextEvent(text="(empty response)")])

        lines = [l for l in raw.strip().splitlines() if l.strip()]
        if not lines:
            return CCResponse(events=[TextEvent(text="(empty response)")])

        # Try NDJSON parsing (stream-json format)
        parsed_lines = []
        for line in lines:
            try:
                parsed_lines.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        if not parsed_lines:
            return CCResponse(events=[TextEvent(text=raw)])

        # If only one object, fall back to legacy single-JSON handling
        if len(parsed_lines) == 1:
            return self._parse_single_json(parsed_lines[0])

        # Collect raw events from the NDJSON stream
        raw_events: list[dict] = []

        for obj in parsed_lines:
            msg_type = obj.get("type", "")
            content = obj.get("content") or obj.get("message", {}).get("content")

            if msg_type == "result":
                continue

            if not isinstance(content, list):
                continue

            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")

                if btype == "tool_use":
                    raw_events.append({
                        "kind": "tool_use",
                        "id": block.get("id", ""),
                        "name": block.get("name", "unknown"),
                        "input": block.get("input", {}),
                    })
                elif btype == "tool_result":
                    raw_events.append({
                        "kind": "tool_result",
                        "tool_use_id": block.get("tool_use_id", ""),
                        "is_error": block.get("is_error", False),
                        "content": block.get("content"),
                    })
                elif btype == "text":
                    text = block.get("text", "").strip()
                    if text:
                        raw_events.append({"kind": "text", "text": text})
                elif btype == "thinking":
                    text = block.get("thinking", "").strip()
                    if text:
                        raw_events.append({"kind": "thinking", "text": text})

        return self._build_response(raw_events)

    def _parse_single_json(self, data: dict) -> CCResponse:
        """Legacy fallback for single JSON object (non-stream format)."""
        if isinstance(data.get("content"), list):
            return self._parse_content_blocks(data["content"])
        if data.get("type") == "result":
            text = data.get("result", "") or "(empty response)"
            return CCResponse(events=[TextEvent(text=text)])
        return CCResponse(events=[TextEvent(text=json.dumps(data)[:500])])

    def _parse_content_blocks(self, content: list) -> CCResponse:
        """Parse content blocks into structured events."""
        events: list = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                name = block.get("name", "unknown")
                input_summary = self._summarize_tool_input(name, block.get("input", {}))
                events.append(ToolCallEvent(
                    tool_id=block.get("id", ""),
                    name=name,
                    input_summary=input_summary,
                    result_text="",
                    is_error=False,
                ))
            elif block.get("type") == "text":
                text = block.get("text", "").strip()
                if text:
                    events.append(TextEvent(text=text))
        if not events:
            return CCResponse(events=[TextEvent(text="(empty response)")])
        return CCResponse(events=events)

    @staticmethod
    def _summarize_tool_input(tool_name: str, input_data: dict) -> str:
        """Create a compact one-line summary of tool input."""
        if tool_name in ("Read", "Write", "NotebookEdit"):
            fp = input_data.get("file_path", "")
            return fp.rsplit("/", 1)[-1] if fp else ""
        if tool_name == "Edit":
            fp = input_data.get("file_path", "")
            return fp.rsplit("/", 1)[-1] if fp else ""
        if tool_name in ("Glob", "Grep"):
            return input_data.get("pattern", "")[:60]
        if tool_name == "Bash":
            cmd = input_data.get("command", "")
            return cmd[:70] + "..." if len(cmd) > 70 else cmd

        for key in ("file_path", "command", "pattern", "query", "url"):
            if key in input_data:
                val = input_data[key]
                return val[:70] + "..." if len(val) > 70 else val
        for v in input_data.values():
            if isinstance(v, str) and v:
                return v[:60] + "..." if len(v) > 60 else v
        return ""

    def _build_response(self, raw_events: list[dict]) -> CCResponse:
        """Pair tool_use/tool_result events and return structured CCResponse."""
        # Index tool_results by tool_use_id for pairing
        results_by_id: dict[str, dict] = {}
        for ev in raw_events:
            if ev["kind"] == "tool_result":
                results_by_id[ev["tool_use_id"]] = ev

        events: list = []
        seen_result_ids: set[str] = set()

        for ev in raw_events:
            if ev["kind"] == "thinking":
                events.append(ThinkingEvent(text=ev["text"]))

            elif ev["kind"] == "tool_use":
                tool_id = ev["id"]
                name = ev["name"]
                input_summary = self._summarize_tool_input(name, ev["input"])
                result_ev = results_by_id.get(tool_id)

                if result_ev:
                    seen_result_ids.add(tool_id)
                    is_error = result_ev.get("is_error", False)
                    result_text = self._extract_tool_result_text(result_ev["content"])
                else:
                    is_error = False
                    result_text = ""

                events.append(ToolCallEvent(
                    tool_id=tool_id,
                    name=name,
                    input_summary=input_summary,
                    result_text=result_text,
                    is_error=is_error,
                ))

            elif ev["kind"] == "tool_result":
                if ev["tool_use_id"] not in seen_result_ids:
                    seen_result_ids.add(ev["tool_use_id"])
                    if ev.get("is_error"):
                        result_text = self._extract_tool_result_text(ev["content"])
                        events.append(ToolCallEvent(
                            tool_id=ev["tool_use_id"],
                            name="unknown",
                            input_summary="",
                            result_text=result_text,
                            is_error=True,
                        ))

            elif ev["kind"] == "text":
                events.append(TextEvent(text=ev["text"]))

        if not events:
            return CCResponse(events=[TextEvent(text="(empty response)")])
        return CCResponse(events=events)

    @staticmethod
    def _extract_tool_result_text(content) -> str:
        """Normalize tool_result content (str, list, dict) into plain text."""
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

    def _restore_states(self) -> None:
        """Restore CC user states from persistent store."""
        for uid, s in self._store.all().items():
            self._user_states[uid] = UserSession(
                mode=s.get("mode", "ciana"),
                active_project=s.get("active_project"),
                active_project_path=s.get("active_project_path"),
                active_session_id=s.get("active_session_id"),
            )
        if self._user_states:
            logger.info("Restored CC state for %d user(s)", len(self._user_states))

    def _persist_user(self, user_id: str) -> None:
        """Persist a single user's CC state."""
        state = self._user_states.get(user_id)
        if state and state.mode == "claude_code":
            self._store.set(user_id, {
                "mode": state.mode,
                "active_project": state.active_project,
                "active_project_path": state.active_project_path,
                "active_session_id": state.active_session_id,
            })

    def _detect_new_session(self, project_encoded: str,
                            known_sessions: set[str]) -> Optional[str]:
        project_dir = self._projects_dir / project_encoded
        if not project_dir.exists():
            return None
        for f in sorted(project_dir.glob("*.jsonl"),
                        key=lambda p: p.stat().st_mtime, reverse=True):
            if f.stem not in known_sessions:
                return f.stem
        return None

    def _peek_cwd(self, jsonl_path: Path) -> str:
        try:
            with open(jsonl_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if cwd := data.get("cwd", ""):
                        return cwd
        except (json.JSONDecodeError, OSError):
            pass
        return ""

    def _parse_conversation(self, jsonl_path: Path) -> Optional[ConversationInfo]:
        session_id = jsonl_path.stem
        first_message = ""
        timestamp = None
        message_count = 0
        git_branch = ""
        cwd = ""

        try:
            with open(jsonl_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if not cwd:
                        cwd = data.get("cwd", "")
                    if not git_branch:
                        git_branch = data.get("gitBranch", "")

                    if timestamp is None and data.get("timestamp"):
                        try:
                            ts = data["timestamp"]
                            if isinstance(ts, str):
                                timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            elif isinstance(ts, (int, float)):
                                timestamp = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                        except (ValueError, OSError):
                            pass

                    msg_type = data.get("type", "")
                    msg_role = data.get("message", {}).get("role", "")
                    if msg_type == "user" or msg_role == "user":
                        message_count += 1
                        if not first_message:
                            content = data.get("message", {}).get("content", "")
                            if isinstance(content, list):
                                texts = [b.get("text", "") for b in content
                                         if isinstance(b, dict) and b.get("type") == "text"]
                                content = " ".join(texts)
                            if isinstance(content, str) and content.strip():
                                first_message = content.strip()[:120]

        except OSError:
            return None

        if timestamp is None:
            try:
                timestamp = datetime.fromtimestamp(jsonl_path.stat().st_mtime, tz=timezone.utc)
            except OSError:
                timestamp = datetime.now(tz=timezone.utc)

        return ConversationInfo(
            session_id=session_id,
            first_message=first_message or "(no preview)",
            timestamp=timestamp,
            message_count=message_count,
            git_branch=git_branch,
            cwd=cwd,
        )
