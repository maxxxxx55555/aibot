import pytest

from app.services.ai.audio import AudioService
from app.services.ai.provider import MockProvider


@pytest.mark.asyncio
async def test_audio_service_transcribe_and_synthesize():
    provider = MockProvider()
    service = AudioService(provider)

    data = b"fake_voice_bytes"
    transcription = await service.transcribe(data, "voice.ogg")
    assert "Расшифровка" in transcription
    assert f"{len(data)} байт" in transcription

    # Test synthesize
    audio_bytes = await service.synthesize("Привет, это тестовый голос!")
    assert isinstance(audio_bytes, bytes)
    assert len(audio_bytes) > 0
    assert audio_bytes.startswith(b"RIFF")  # WAV header signature


@pytest.mark.asyncio
async def test_audio_service_empty_input():
    provider = MockProvider()
    service = AudioService(provider)

    assert await service.transcribe(b"") == ""

    synth_empty = await service.synthesize("")
    assert isinstance(synth_empty, bytes)
    assert len(synth_empty) > 0
