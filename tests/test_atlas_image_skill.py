"""Tests for the Atlas Cloud image skill client."""

import importlib.util
from pathlib import Path

import pytest

CLIENT_PATH = Path(__file__).parents[1] / "skills" / "atlas-image-gen" / "atlas_client.py"
SPEC = importlib.util.spec_from_file_location("atlas_image_client", CLIENT_PATH)
assert SPEC and SPEC.loader
client = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(client)


def test_generation_submits_once_then_polls_result_url():
    calls = []
    responses = iter(
        [
            {
                "data": {
                    "id": "pred-1",
                    "status": "queued",
                    "urls": {"result": "/api/v1/model/result/pred-1"},
                }
            },
            {"data": {"id": "pred-1", "status": "processing"}},
            {
                "data": {
                    "id": "pred-1",
                    "status": "succeeded",
                    "outputs": ["https://cdn.example/image.jpeg"],
                }
            },
        ]
    )

    def request(method, url, api_key, payload=None, timeout=60):
        calls.append((method, url, api_key, payload, timeout))
        return next(responses)

    output = client.generate_image(
        "secret",
        "a lighthouse",
        request_json=request,
        sleep=lambda _: None,
    )

    assert output == "https://cdn.example/image.jpeg"
    assert [call[0] for call in calls] == ["POST", "GET", "GET"]
    assert calls[0][3]["model"] == client.DEFAULT_MODEL
    assert calls[0][3]["size"] == "1024*1024"
    assert calls[1][1] == "https://api.atlascloud.ai/api/v1/model/result/pred-1"


def test_generation_post_is_not_retried():
    calls = 0

    def request(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise client.AtlasHTTPError(503, "unavailable")

    with pytest.raises(client.AtlasHTTPError):
        client.generate_image(
            "secret",
            "a lighthouse",
            request_json=request,
            sleep=lambda _: None,
        )

    assert calls == 1
