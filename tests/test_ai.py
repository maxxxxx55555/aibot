"""MockProvider, фабрика провайдера, сборка контекста (§6.1, §6.3)."""

from __future__ import annotations

from app.services.ai.context import approx_tokens, build_context
from app.services.ai.provider import MockProvider, build_provider


async def test_mock_provider_chat():
    provider = MockProvider(embedding_dim=64)
    reply = await provider.chat([{"role": "user", "content": "Как оплатить?"}])
    assert reply.content.startswith("[MOCK]")
    assert "Как оплатить?" in reply.content
    assert reply.tokens > 0


async def test_mock_provider_deterministic():
    p = MockProvider(embedding_dim=64)
    r1 = await p.chat([{"role": "user", "content": "тест"}])
    r2 = await p.chat([{"role": "user", "content": "тест"}])
    assert r1.content == r2.content


async def test_mock_embeds_normalized():
    p = MockProvider(embedding_dim=64)
    vecs = await p.embed(["кофе", "кофе", "чай"])
    assert len(vecs) == 3
    assert all(len(v) == 64 for v in vecs)
    assert abs(sum(v * v for v in vecs[0]) - 1.0) < 1e-6  # нормирован
    assert vecs[0] == vecs[1]  # детерминизм
    assert vecs[0] != vecs[2]


def test_build_provider_mock_without_key(settings):
    assert settings.use_mock_llm is True
    assert isinstance(build_provider(settings), MockProvider)


def test_build_provider_real_with_key(settings):
    settings = settings.model_copy(update={"llm_api_key": "sk-test"})
    provider = build_provider(settings)
    assert not isinstance(provider, MockProvider)


def test_approx_tokens():
    assert approx_tokens("") == 1
    assert approx_tokens("a" * 400) == 100


def test_build_context_respects_budget():
    system = "S" * 100  # 25 токенов
    history = [(role, "x" * 400) for role in ["user", "assistant"]] * 10  # много
    messages = build_context(system, history, context_window=20, token_budget=200)
    assert messages[0]["role"] == "system"
    body = messages[1:]
    assert len(body) < 20  # обрезано по бюджету
    # Хронология сохранена, хвост остался
    assert body[-1]["content"] == history[-1][1]


def test_build_context_empty_history():
    messages = build_context("sys", [], 10, 100)
    assert messages == [{"role": "system", "content": "sys"}]


def test_openai_compat_provider_fallback_init(settings):
    from app.services.ai.provider import OpenAICompatProvider

    settings = settings.model_copy(
        update={
            "llm_api_key": "sk-primary",
            "llm_fallback_base_url": "https://fallback.example.com/v1",
            "llm_fallback_api_key": "sk-fallback",
            "llm_fallback_model": "fallback-model",
        }
    )
    provider = OpenAICompatProvider(settings)
    assert provider.fallback is not None
    assert provider.fallback.model == "fallback-model"
    assert provider.fallback._semaphore is provider._semaphore


async def test_openai_compat_provider_fallback_execution(settings):
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.ai.provider import OpenAICompatProvider

    settings = settings.model_copy(
        update={
            "llm_api_key": "sk-primary",
            "llm_fallback_base_url": "https://fallback.example.com/v1",
            "llm_fallback_api_key": "sk-fallback",
            "llm_fallback_model": "fallback-model",
            "llm_max_retries": 1,
        }
    )
    provider = OpenAICompatProvider(settings)

    primary_err = Exception("Primary failed")
    primary_err.status_code = 500  # type: ignore[attr-defined]

    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="Fallback answer"))]
    mock_resp.usage = MagicMock(total_tokens=15)

    mock_fallback_create = AsyncMock(return_value=mock_resp)

    with patch.object(
        provider.client.chat.completions, "create", side_effect=primary_err
    ), patch.object(
        provider.fallback.client.chat, "completions", MagicMock(create=mock_fallback_create)
    ):
        reply = await provider.chat([{"role": "user", "content": "hello"}])
        assert reply.content == "Fallback answer"
        assert reply.tokens == 15
        mock_fallback_create.assert_called_once_with(
            model="fallback-model", messages=[{"role": "user", "content": "hello"}]
        )