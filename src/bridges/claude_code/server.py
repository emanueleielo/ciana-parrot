#!/usr/bin/env python3
"""Claude Code bridge — runs on host, executes claude CLI for the Docker container."""

import json
import os
import signal
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# Try loading from config.yaml (single source of truth), fall back to env vars
# for standalone usage without config file.
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from src.config import load_config
    _cfg = load_config()
    PORT = _cfg.claude_code.bridge_port
    TOKEN = _cfg.claude_code.bridge_token or ""
except Exception:
    _cfg = None
    PORT = int(os.environ.get("CC_BRIDGE_PORT", "9842"))
    TOKEN = os.environ.get("CC_BRIDGE_TOKEN", "")


class BridgeHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok"})
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

        cmd = data.get("cmd", [])
        cwd = data.get("cwd")
        timeout = data.get("timeout", 0)

        if not cmd:
            self._respond(400, {"error": "missing cmd"})
            return

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
        except subprocess.TimeoutExpired:
            self._respond(200, {
                "stdout": "", "stderr": "Command timed out", "returncode": -1,
            })
        except Exception as e:
            self._respond(500, {"error": str(e)})

    # --- Helpers ---

    def _check_auth(self) -> bool:
        import hmac
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

    def _claude_version(self) -> str:
        try:
            r = subprocess.run(
                ["claude", "--version"], capture_output=True, text=True, timeout=10)
            return r.stdout.strip() if r.returncode == 0 else "unavailable"
        except Exception:
            return "unavailable"

    def log_message(self, format, *args):
        sys.stderr.write(f"[cc-bridge] {format % args}\n")


if __name__ == "__main__":
    print(f"Claude Code bridge on 0.0.0.0:{PORT}")
    if TOKEN:
        print("Auth: enabled")
    else:
        print("Auth: disabled (set CC_BRIDGE_TOKEN to enable)")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), BridgeHandler)
    server.daemon_threads = True

    stop = threading.Event()

    def _shutdown(signum, _frame):
        print("\nShutting down bridge...")
        stop.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    stop.wait()
    server.shutdown()
    server.server_close()
    print("Bridge stopped.")
