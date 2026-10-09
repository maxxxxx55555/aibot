"""AI-провайдеры: OpenAI-совместимый (GLM/OpenAI/прокси) и Mock для dev/test (§6.1)."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import random
from dataclasses import dataclass
from typing import Protocol

from app.config import Settings

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


class LLMUnavailable(Exception):
    """Все ретраи/провайдеры исчерпаны — graceful degradation (§8.3)."""


class AIProvider(Protocol):
    async def chat(self, messages: list[dict[str, str]]) -> Reply: ...
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str: ...
    async def synthesize_speech(self, text: str, voice: str = "alloy") -> bytes: ...


@dataclass(frozen=True)
class Reply:
    content: str
    tokens: int = 0


class MockProvider:
    """Детерминированные ответы без внешних ключей — dev/test/CI."""

    def __init__(self, embedding_dim: int = 1024) -> None:
        self.embedding_dim = embedding_dim

    async def chat(self, messages: list[dict[str, str]]) -> Reply:
        await asyncio.sleep(0.05)
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        content = (
            f"[MOCK] Принял запрос: «{last_user[:200]}». "
            f"Как AI-Сотрудник: квалифицирую лид, отвечу на вопрос клиента "
            f"или запишу на консультацию. Подключите LLM_API_KEY для реальных ответов."
        )
        return Reply(content=content, tokens=len(content) // 4)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._fake_vector(t) for t in texts]

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        await asyncio.sleep(0.05)
        return f"[MOCK] Расшифровка голосового сообщения ({len(audio_bytes)} байт)"

    async def synthesize_speech(self, text: str, voice: str = "alloy") -> bytes:
        await asyncio.sleep(0.05)
        from app.services.ai.audio import _generate_mock_wav
        return _generate_mock_wav(1.0)

    def _fake_vector(self, text: str) -> list[float]:
        """Детерминированный нормированный вектор нужной размерности."""
        values: list[float] = []
        counter = 0
        seed = text.encode()
        while len(values) < self.embedding_dim:
            h = hashlib.sha256(seed + counter.to_bytes(4, "little")).digest()
            values.extend(b / 255.0 for b in h)
            counter += 1
        values = values[: self.embedding_dim]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]


class OpenAICompatProvider:
    """AsyncOpenAI с ретраями (backoff+джиттер) и опциональным fallback (§8.1-8.2).

    Работает с любым OpenAI-совместимым API: Groq, OpenRouter (:free модели),
    OpenAI, GLM — base_url берётся из пресета llm_provider (см. config.py).
    """

    def __init__(self, settings: Settings) -> None:
        from openai import AsyncOpenAI

        self.settings = settings
        self.model = settings.resolved_llm_model
        self.client = AsyncOpenAI(
            base_url=settings.resolved_llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout,
            max_retries=0,  # ретраи контролируем сами
        )
        self.fallback: OpenAICompatProvider | None = None
        if settings.llm_fallback_base_url and settings.llm_fallback_api_key:
            self.fallback = OpenAICompatProvider.__new__(OpenAICompatProvider)
            self.fallback.settings = settings
            self.fallback.client = AsyncOpenAI(
                base_url=settings.llm_fallback_base_url,
                api_key=settings.llm_fallback_api_key,
                timeout=settings.llm_timeout,
                max_retries=0,
            )
            self.fallback.fallback = None
        self._semaphore = asyncio.Semaphore(20)  # глобальный лимит конкурентных запросов

    async def chat(self, messages: list[dict[str, str]]) -> Reply:
        try:
            return await self._chat_with_retries(self, self.model, messages)
        except LLMUnavailable:
            if self.fallback is not None:
                logger.warning("LLM primary failed, switching to fallback")
                return await self._chat_with_retries(
                    self.fallback, self.settings.llm_fallback_model, messages
                )
            raise

    async def _chat_with_retries(
        self, provider: OpenAICompatProvider, model: str, messages: list[dict[str, str]]
    ) -> Reply:
        last_exc: Exception | None = None
        for attempt in range(1, self.settings.llm_max_retries + 1):
            try:
                async with self._semaphore:
                    resp = await provider.client.chat.completions.create(
                        model=model, messages=messages  # type: ignore[arg-type]
                    )
                content = resp.choices[0].message.content or ""
                tokens = resp.usage.total_tokens if resp.usage else len(content) // 4
                return Reply(content=content, tokens=tokens)
            except Exception as exc:
                status = getattr(exc, "status_code", None)
                if status not in RETRYABLE_STATUS and status is not None:
                    logger.error("LLM non-retryable error %s: %s", status, type(exc).__name__)
                    raise LLMUnavailable(str(exc)) from exc
                last_exc = exc
                delay = min(2 ** (attempt - 1), 8) * (1 + random.random() / 2)
                logger.warning(
                    "LLM retry %d/%d after %.1fs: %s",
                    attempt, self.settings.llm_max_retries, delay, type(exc).__name__,
                )
                await asyncio.sleep(delay)
        raise LLMUnavailable(str(last_exc))

    async def embed(self, texts: list[str]) -> list[list[float]]:
        resp = await self.client.embeddings.create(
            model=self.settings.embedding_model, input=texts
        )
        return [item.embedding for item in resp.data]

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        from io import BytesIO
        file_obj = BytesIO(audio_bytes)
        file_obj.name = filename
        try:
            resp = await self.client.audio.transcriptions.create(
                model="whisper-1",
                file=file_obj,
            )
            return resp.text or ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("Whisper transcription error: %s", exc)
            return "[Не удалось распознать голосовое сообщение]"

    async def synthesize_speech(self, text: str, voice: str = "alloy") -> bytes:
        try:
            response = await self.client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text[:4096],
            )
            return response.content
        except Exception as exc:  # noqa: BLE001
            logger.warning("TTS speech synthesis error: %s", exc)
            from app.services.ai.audio import _generate_mock_wav
            return _generate_mock_wav(1.0)


def build_provider(settings: Settings) -> AIProvider:
    """Фабрика провайдера: без ключа — MockProvider (§6.1)."""
    if settings.use_mock_llm:
        logger.warning("LLM в MOCK-режиме: реальные ответы отключены")
        return MockProvider(embedding_dim=settings.embedding_dim)
    return OpenAICompatProvider(settings)