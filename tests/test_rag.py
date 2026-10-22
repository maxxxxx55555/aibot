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


async def test_repo_count_queries(session):
    u1 = await UserRepo(session).get_or_create(101)
    u2 = await UserRepo(session).get_or_create(102)
    user_repo = UserRepo(session)
    knowledge_repo = KnowledgeRepo(session)

    initial_users = await user_repo.count_all()
    assert initial_users >= 2

    assert await knowledge_repo.count_for_owner(u1.id) == 0
    await knowledge_repo.add_chunk(u1.id, "chunk 1")
    await knowledge_repo.add_chunk(u1.id, "chunk 2")
    assert await knowledge_repo.count_for_owner(u1.id) == 2
    assert await knowledge_repo.count_for_owner(u2.id) == 0


async def test_kb_knowledge_menu_button(session, settings):
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
    from aiogram.types import Chat
    from aiogram.types import User as TgUser

    from app.bot.handlers.menu import kb_knowledge

    user = await UserRepo(session).get_or_create(555)
    await UserRepo(session).set_plan(user, "pro", 30)
    await KnowledgeRepo(session).add_chunk(user.id, "Информация 1")
    await KnowledgeRepo(session).add_chunk(user.id, "Информация 2")

    sent_messages = []

    class FakeMessage:
        def __init__(self) -> None:
            self.chat = Chat(id=555, type="private")
            self.from_user = TgUser(id=555, is_bot=False, first_name="Test")

        async def answer(self, text, reply_markup=None, link_preview_options=None):
            sent_messages.append(text)

    storage = MemoryStorage()
    key = StorageKey(bot_id=123, chat_id=555, user_id=555)
    state = FSMContext(storage=storage, key=key)

    msg = FakeMessage()
    await kb_knowledge(msg, user, session, state, settings)

    assert sent_messages
    assert "Загружено фрагментов: <b>2</b>" in sent_messages[0]