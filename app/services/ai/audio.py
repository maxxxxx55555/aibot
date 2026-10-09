"""Сервис обработки аудио: Speech-to-Text (STT, распознавание голоса) и Text-to-Speech (TTS, озвучка)."""

from __future__ import annotations

import io
import logging
import wave

logger = logging.getLogger(__name__)

# Минимальный суррогатный WAV-файл тишины для mock-режима/тестов
def _generate_mock_wav(duration_s: float = 1.0, sample_rate: int = 16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        n_frames = int(sample_rate * duration_s)
        wav.writeframes(b"\x00\x00" * n_frames)
    return buffer.getvalue()


class AudioService:
    """Сервис преобразования аудио: STT (транскрипция) и TTS (синтез речи)."""

    def __init__(self, provider: object) -> None:
        self.provider = provider

    async def transcribe(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        """Расшифровка голосового сообщения в текст."""
        if not audio_bytes:
            return ""
        if hasattr(self.provider, "transcribe_audio"):
            try:
                return await self.provider.transcribe_audio(audio_bytes, filename)
            except Exception:
                logger.exception("Ошибка расшифровки аудио провайдером")
                return "[Не удалось распознать голосовое сообщение]"
        return f"[MOCK] Расшифрованное голосовое сообщение ({len(audio_bytes)} байт)"

    async def synthesize(self, text: str, voice: str = "alloy") -> bytes:
        """Синтез речи из текста (возвращает байты звукового файла)."""
        if not text.strip():
            return _generate_mock_wav(0.5)
        if hasattr(self.provider, "synthesize_speech"):
            try:
                return await self.provider.synthesize_speech(text, voice)
            except Exception:
                logger.exception("Ошибка генерации речи провайдером")
                return _generate_mock_wav(1.0)
        return _generate_mock_wav(1.0)
