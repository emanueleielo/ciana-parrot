"""Multi-provider audio transcription service (Groq / OpenAI Whisper API)."""

import logging
from typing import Optional

import httpx

from .config import TranscriptionConfig

logger = logging.getLogger(__name__)

ENDPOINTS = {
    "groq": "https://api.groq.com/openai/v1/audio/transcriptions",
    "openai": "https://api.openai.com/v1/audio/transcriptions",
}

# Module-level config, set by init_transcription()
_provider: Optional[str] = None
_model: Optional[str] = None
_api_key: Optional[str] = None
_base_url: Optional[str] = None
_timeout: int = 30


def init_transcription(config: TranscriptionConfig) -> None:
    """Initialize transcription with config values."""
    global _provider, _model, _api_key, _base_url, _timeout
    _provider = config.provider
    _model = config.model
    _api_key = config.api_key
    _base_url = config.base_url
    _timeout = config.timeout


def is_configured() -> bool:
    """Check if transcription is properly configured (has API key)."""
    return bool(_api_key)


async def transcribe(
    audio_bytes: bytes,
    filename: str = "audio.ogg",
    mime_type: str = "audio/ogg",
) -> str:
    """Transcribe audio bytes via the configured Whisper API.

    Returns the transcribed text, or raises on error.
    """
    if not _api_key:
        raise RuntimeError("Transcription not configured (missing API key)")

    url = _base_url or ENDPOINTS.get(_provider, ENDPOINTS["groq"])

    async with httpx.AsyncClient(timeout=_timeout) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {_api_key}"},
            data={"model": _model},
            files={"file": (filename, audio_bytes, mime_type)},
        )
    resp.raise_for_status()
    result = resp.json()
    return result.get("text", "")
