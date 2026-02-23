"""Async HTTP client for the host gateway."""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class GatewayResult:
    """Result from a gateway command execution."""
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    error: str = ""


class GatewayClient:
    """Async client for communicating with the host gateway server."""

    def __init__(self, base_url: str, token: Optional[str] = None):
        self._base_url = base_url.rstrip("/")
        self._token = token

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def execute(
        self,
        bridge: str,
        cmd: list[str],
        cwd: Optional[str] = None,
        timeout: int = 0,
    ) -> GatewayResult:
        """Execute a command via the gateway.

        Args:
            bridge: Bridge name (e.g. "claude-code", "apple-notes").
            cmd: Command as list of strings.
            cwd: Working directory on the host.
            timeout: Subprocess timeout in seconds. 0 = no timeout.
        """
        # HTTP timeout: no limit if subprocess timeout is 0, otherwise add buffer
        http_timeout = httpx.Timeout(None) if timeout == 0 else timeout + 10

        payload: dict = {"bridge": bridge, "cmd": cmd, "timeout": timeout}
        if cwd:
            payload["cwd"] = cwd

        try:
            async with httpx.AsyncClient(timeout=http_timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/execute",
                    json=payload,
                    headers=self._headers(),
                )
            if resp.status_code == 401:
                return GatewayResult(error="Gateway auth failed. Check GATEWAY_TOKEN.")
            if resp.status_code == 403:
                data = resp.json()
                return GatewayResult(error=data.get("error", f"Forbidden (403)"))
            if not resp.is_success:
                return GatewayResult(error=f"Gateway returned HTTP {resp.status_code}")
            data = resp.json()
        except httpx.ConnectError:
            return GatewayResult(
                error="Cannot connect to host gateway. Is the gateway server running?"
            )
        except httpx.TimeoutException:
            return GatewayResult(error="Gateway request timed out.")
        except Exception as e:
            logger.exception("Gateway request failed")
            return GatewayResult(error=f"Gateway error: {e}")

        return GatewayResult(
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            returncode=data.get("returncode", 0),
        )

    async def health(self) -> tuple[bool, dict]:
        """Check gateway health. Returns (ok, response_data)."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._base_url}/health",
                    headers=self._headers(),
                )
            if resp.status_code == 200:
                return True, resp.json()
            return False, {"error": f"HTTP {resp.status_code}"}
        except httpx.ConnectError:
            return False, {"error": "Cannot connect to host gateway"}
        except Exception as e:
            return False, {"error": str(e)}
