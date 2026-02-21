"""Tests for src.transcription — init, is_configured, transcribe."""

from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest

from src.transcription import (
    ENDPOINTS,
    init_transcription,
    is_configured,
    transcribe,
)
from src.config import TranscriptionConfig


class TestInitTranscription:
    def test_sets_globals(self):
        cfg = TranscriptionConfig(
            enabled=True,
            provider="groq",
            model="whisper-large-v3-turbo",
            api_key="gsk_test",
            timeout=15,
        )
        init_transcription(cfg)

        from src import transcription
        assert transcription._provider == "groq"
        assert transcription._model == "whisper-large-v3-turbo"
        assert transcription._api_key == "gsk_test"
        assert transcription._timeout == 15

    def test_custom_base_url(self):
        cfg = TranscriptionConfig(
            provider="openai",
            api_key="sk_test",
            base_url="https://custom.api/v1/audio/transcriptions",
        )
        init_transcription(cfg)

        from src import transcription
        assert transcription._base_url == "https://custom.api/v1/audio/transcriptions"


class TestIsConfigured:
    def test_not_configured_by_default(self):
        assert is_configured() is False

    def test_configured_with_api_key(self):
        init_transcription(TranscriptionConfig(api_key="gsk_test"))
        assert is_configured() is True

    def test_not_configured_without_api_key(self):
        init_transcription(TranscriptionConfig(api_key=None))
        assert is_configured() is False


class TestTranscribe:
    @pytest.mark.asyncio
    async def test_success(self):
        init_transcription(TranscriptionConfig(
            provider="groq", api_key="gsk_test", model="whisper-large-v3-turbo",
        ))

        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "Hello world"}
        mock_response.raise_for_status = MagicMock()

        with patch("src.transcription.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await transcribe(b"audio-bytes", "voice.ogg")

        assert result == "Hello world"
        mock_client.post.assert_awaited_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == ENDPOINTS["groq"]

    @pytest.mark.asyncio
    async def test_openai_endpoint(self):
        init_transcription(TranscriptionConfig(
            provider="openai", api_key="sk_test", model="whisper-1",
        ))

        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "Transcribed"}
        mock_response.raise_for_status = MagicMock()

        with patch("src.transcription.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await transcribe(b"audio-bytes")

        assert result == "Transcribed"
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == ENDPOINTS["openai"]

    @pytest.mark.asyncio
    async def test_custom_base_url_used(self):
        init_transcription(TranscriptionConfig(
            provider="groq", api_key="gsk_test",
            base_url="https://custom.api/transcribe",
        ))

        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "Custom"}
        mock_response.raise_for_status = MagicMock()

        with patch("src.transcription.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await transcribe(b"audio-bytes")

        assert result == "Custom"
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == "https://custom.api/transcribe"

    @pytest.mark.asyncio
    async def test_empty_result(self):
        init_transcription(TranscriptionConfig(
            provider="groq", api_key="gsk_test",
        ))

        mock_response = MagicMock()
        mock_response.json.return_value = {"text": ""}
        mock_response.raise_for_status = MagicMock()

        with patch("src.transcription.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await transcribe(b"audio-bytes")

        assert result == ""

    @pytest.mark.asyncio
    async def test_api_error_raises(self):
        init_transcription(TranscriptionConfig(
            provider="groq", api_key="gsk_test",
        ))

        with patch("src.transcription.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(httpx.HTTPStatusError):
                await transcribe(b"audio-bytes")

    @pytest.mark.asyncio
    async def test_mime_type_passed_through(self):
        """Verify that custom mime_type is forwarded to the API."""
        init_transcription(TranscriptionConfig(
            provider="openai", api_key="sk_test", model="whisper-1",
        ))

        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "MP3 audio"}
        mock_response.raise_for_status = MagicMock()

        with patch("src.transcription.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await transcribe(
                b"mp3-bytes", filename="song.mp3", mime_type="audio/mpeg",
            )

        assert result == "MP3 audio"
        call_kwargs = mock_client.post.call_args
        # files param: {"file": (filename, bytes, mime_type)}
        files_arg = call_kwargs[1]["files"]
        assert files_arg["file"][0] == "song.mp3"
        assert files_arg["file"][2] == "audio/mpeg"

    @pytest.mark.asyncio
    async def test_not_configured_raises(self):
        # No init_transcription called — _api_key is None
        with pytest.raises(RuntimeError, match="not configured"):
            await transcribe(b"audio-bytes")
