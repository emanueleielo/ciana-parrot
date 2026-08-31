"""Minimal Atlas Cloud image generation client."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

ATLAS_API_BASE = "https://api.atlascloud.ai/api/v1"
DEFAULT_MODEL = "black-forest-labs/flux-schnell"


class AtlasHTTPError(RuntimeError):
    """Atlas Cloud HTTP error with its status code."""

    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"Atlas Cloud API failed ({status_code}): {body}")
        self.status_code = status_code


def _request_json(
    method: str,
    url: str,
    api_key: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        method=method,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ciana-parrot-atlas-image-skill/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode(errors="replace")
        raise AtlasHTTPError(exc.code, error_body) from exc


def _response_data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data", payload)
    return data if isinstance(data, dict) else {}


def _outputs(payload: dict[str, Any]) -> list[str]:
    data = _response_data(payload)
    outputs = data.get("outputs", data.get("output", []))
    if isinstance(outputs, str):
        return [outputs]
    if isinstance(outputs, list):
        return [item for item in outputs if isinstance(item, str)]
    return []


def generate_image(
    api_key: str,
    prompt: str,
    model: str = DEFAULT_MODEL,
    size: str = "1024*1024",
    *,
    request_json: Callable[..., dict[str, Any]] = _request_json,
    sleep: Callable[[float], None] = time.sleep,
    max_polls: int = 100,
) -> str:
    """Submit one Atlas image generation and return its first output URL."""
    submitted = request_json(
        "POST",
        f"{ATLAS_API_BASE}/model/generateImage",
        api_key,
        {
            "model": model,
            "prompt": prompt,
            "size": size.replace("x", "*"),
            "num_images": 1,
            "enable_sync_mode": False,
        },
        300,
    )

    immediate_outputs = _outputs(submitted)
    if immediate_outputs:
        return immediate_outputs[0]

    data = _response_data(submitted)
    prediction_id = data.get("id") or data.get("request_id")
    if not prediction_id:
        raise RuntimeError("Atlas Cloud response did not include a prediction ID")

    urls = data.get("urls") if isinstance(data.get("urls"), dict) else {}
    result_url = urls.get("result") or f"{ATLAS_API_BASE}/model/result/{prediction_id}"
    result_url = urllib.parse.urljoin(f"{ATLAS_API_BASE}/", result_url)

    for attempt in range(max_polls):
        try:
            result = request_json("GET", result_url, api_key, None, 60)
        except (AtlasHTTPError, urllib.error.URLError) as exc:
            transient = isinstance(exc, urllib.error.URLError) or exc.status_code >= 500
            if not transient or attempt == max_polls - 1:
                raise
            sleep(min(3 * (2 ** min(attempt, 3)), 15))
            continue

        result_outputs = _outputs(result)
        if result_outputs:
            return result_outputs[0]

        status = str(_response_data(result).get("status", "")).lower()
        if status in {"failed", "canceled", "cancelled"}:
            raise RuntimeError(f"Atlas Cloud prediction {prediction_id} {status}")
        if attempt < max_polls - 1:
            sleep(3)

    raise RuntimeError(
        f"Atlas Cloud prediction {prediction_id} did not finish after {max_polls} polls"
    )
