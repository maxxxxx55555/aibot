"""Репозитории сообщений и RAG: chunking, сохранение, retrieval (§3, §6.4)."""

from __future__ import annotations

from app.db.repo.knowledge import KnowledgeRepo
from app.db.repo.messages import MessageRepo
from app.db.repo.users import UserRepo
from app.services.ai.provider import MockProvider
from app.services.ai.rag import RagService, chunk_text


async def test_message_recent_order_and_limit(session):
    user = await UserRepo(session).get_or_create(1)
    repo = MessageRepo(session)
    for i in range(10):
        await repo.add_message(user.id, "user" if i % 2 == 0 else "assistant", f"msg-{i}")
    rows = await repo.recent(user.id, limit=4)
    assert [r.content for r in rows] == ["msg-6", "msg-7", "msg-8", "msg-9"]


async def test_delete_history(session):
    user = await UserRepo(session).get_or_create(2)
    repo = MessageRepo(session)
    await repo.add_message(user.id, "user", "hi")
    assert await repo.delete_history(user.id) == 1
    assert await repo.recent(user.id, 10) == []


def test_chunk_text():
    assert chunk_text("  ", 100, 10) == []
    assert chunk_text("короткий", 100, 10) == ["короткий"]
    text = "a" * 250
    chunks = chunk_text(text, 100, 50)
    # step=50: 0-100, 50-150, 100-200, 150-250
    assert len(chunks) == 4
    assert chunks[0] == "a" * 100
    assert chunks[-1] == "a" * 100
    assert text.startswith(chunks[0])


async def test_rag_add_and_retrieve(session, settings):
    rag = RagService(MockProvider(embedding_dim=settings.embedding_dim), settings)
    user = await UserRepo(session).get_or_create(5)

    added = await rag.add_text(session, user.id, "Мы кофейня на Ленина 5. Капучино — 250 рублей.")
    assert added == 1

    # Поиск по близкому тексту: сам чанк должен быть топ-результатом
    results = await rag.retrieve(session, user.id, "Капучино цена кофейня")
    assert len(results) == 1
    assert "Капучино" in results[0]


async def test_rag_empty_base_returns_empty(session, settings):
    rag = RagService(MockProvider(embedding_dim=settings.embedding_dim), settings)
    user = await UserRepo(session).get_or_create(6)
    assert await rag.retrieve(session, user.id, "любой запрос") == []


async def test_rag_isolated_per_owner(session, settings):
    rag = RagService(MockProvider(embedding_dim=settings.embedding_dim), settings)
    u1 = await UserRepo(session).get_or_create(7)
    u2 = await UserRepo(session).get_or_create(8)
    await rag.add_text(session, u1.id, "Секретные данные владельца 1")
    assert await rag.retrieve(session, u2.id, "секретные данные") == []
    repo = KnowledgeRepo(session)
    assert len(await repo.for_owner(u1.id)) == 1
    assert len(await repo.for_owner(u2.id)) == 0


async def test_forget_me_cascades(session, settings):
    rag = RagService(MockProvider(embedding_dim=settings.embedding_dim), settings)
    user = await UserRepo(session).get_or_create(9)
    await rag.add_text(session, user.id, "данные")
    repo = KnowledgeRepo(session)
    await repo.delete_for_owner(user.id)
    assert await repo.for_owner(user.id) == []


async def test_cb_knowledge_edits_message_once(session, settings, monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    from app.bot.handlers.knowledge import cb_knowledge

    user = await UserRepo(session).get_or_create(10)
    user.plan = "pro"
    await session.commit()

    callback = AsyncMock()
    callback.message = MagicMock()
    callback.answer = AsyncMock()

    edited_count = 0

    async def mock_safe_edit(msg, text, reply_markup=None):
        nonlocal edited_count
        edited_count += 1

    monkeypatch.setattr("app.bot.handlers.knowledge.safe_edit", mock_safe_edit)

    await cb_knowledge(callback, user, session, settings)

    assert edited_count == 1
    callback.answer.assert_called_once()