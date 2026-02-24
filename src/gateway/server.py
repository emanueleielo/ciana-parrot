#!/usr/bin/env python3
"""Unified host gateway — runs on host, executes allowed commands for the Docker container."""

import hmac
import json
import os
import signal
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# Build allowlists from config, with standalone fallback.
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    from src.config import load_config
    _cfg = load_config()
    PORT = _cfg.gateway.port
    TOKEN = _cfg.gateway.token or ""
    _ALLOWLISTS: dict[str, set[str]] = {}
    for bridge_name, bdef in _cfg.gateway.bridges.items():
        _ALLOWLISTS[bridge_name] = set(bdef.allowed_commands)
except Exception as e:
    import traceback
    sys.stderr.write(f"[gateway] WARNING: Failed to load config ({e}), using env-var fallback\n")
    traceback.print_exc(file=sys.stderr)
    _cfg = None
    PORT = int(os.environ.get("GATEWAY_PORT", os.environ.get("CC_BRIDGE_PORT", "9842")))
    TOKEN = os.environ.get("GATEWAY_TOKEN", os.environ.get("CC_BRIDGE_TOKEN", ""))
    # Standalone fallback: only claude-code bridge with "claude" command
    _ALLOWLISTS = {"claude-code": {"claude"}}


def validate_request(data: dict, allowlists: dict[str, set[str]]) -> tuple[bool, int, str]:
    """Validate a request against bridge allowlists.

    Returns (ok, http_status, error_message). If ok is True, status/message are unused.
    """
    bridge = data.get("bridge")
    if not bridge:
        return False, 400, "missing 'bridge' field"

    if bridge not in allowlists:
        return False, 403, f"unknown bridge: {bridge}"

    cmd = data.get("cmd", [])
    if not cmd:
        return False, 400, "missing cmd"

    # Validate command basename against allowlist
    cmd_basename = os.path.basename(cmd[0])
    if cmd_basename not in allowlists[bridge]:
        return False, 403, f"command '{cmd_basename}' not allowed for bridge '{bridge}'"

    return True, 0, ""


class GatewayHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {
                "status": "ok",
                "bridges": list(_ALLOWLISTS.keys()),
            })
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/execute":
            self._respond(404, {"error": "not found"})
            return
        if not self._check_auth():
            return

        data = self._read_json()
        if data is None:
            return

        # Validate bridge + command against allowlists
        ok, status, error = validate_request(data, _ALLOWLISTS)
        if not ok:
            self._respond(status, {"error": error})
            return

        cmd = data["cmd"]
        cwd = data.get("cwd")
        timeout = data.get("timeout", 0)

        env = os.environ.copy()
        env.pop("CLAUDE_CODE", None)
        env.pop("CLAUDECODE", None)
        effective_cwd = cwd if cwd and os.path.isdir(cwd) else None
        effective_timeout = None if timeout == 0 else timeout

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                cwd=effective_cwd, timeout=effective_timeout, env=env,
            )
            self._respond(200, {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            })
        except FileNotFoundError:
            self._respond(200, {
                "stdout": "",
                "stderr": f"Command '{cmd[0]}' not found on host. Install it first.",
                "returncode": 127,
            })
        except subprocess.TimeoutExpired:
            self._respond(200, {
                "stdout": "", "stderr": "Command timed out", "returncode": -1,
            })
        except Exception as e:
            self._respond(500, {"error": str(e)})

    # --- Helpers ---

    def _check_auth(self) -> bool:
        if not TOKEN:
            return True
        auth = self.headers.get("Authorization", "")
        expected = f"Bearer {TOKEN}"
        if hmac.compare_digest(auth, expected):
            return True
        self._respond(401, {"error": "unauthorized"})
        return False

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._respond(400, {"error": "invalid JSON"})
            return None

    def _respond(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        sys.stderr.write(f"[gateway] {format % args}\n")


if __name__ == "__main__":
    print(f"Host gateway on 0.0.0.0:{PORT}")
    print(f"Bridges: {', '.join(_ALLOWLISTS.keys()) or '(none)'}")
    if TOKEN:
        print("Auth: enabled")
    else:
        print("Auth: disabled (set GATEWAY_TOKEN to enable)")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), GatewayHandler)
    server.daemon_threads = True

    stop = threading.Event()

    def _shutdown(signum, _frame):
        print("\nShutting down gateway...")
        stop.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    stop.wait()
    server.shutdown()
    server.server_close()
    print("Gateway stopped.")
