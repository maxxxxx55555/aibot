"""Интеграционные проверки: реальный Dispatcher + фейковая сессия Bot API.

Прогоняем апдейты через `dp.feed_update` — те же middlewares, роутеры и сервисы,
что в проде, но без сети: все вызовы Telegram перехватывает FakeSession.
Это проверяет всю связку «апдейт → middleware → хендлер → БД → ответ».
"""

from __future__ import annotations

from datetime import UTC, datetime

from aiogram.client.session.base import BaseSession
from aiogram.methods import SendChatAction, SendMessage
from aiogram.types import Chat, Message, PhotoSize, Update
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.repo.users import UserRepo

BOT_TOKEN = "123456:TEST-TOKEN"


class FakeSession(BaseSession):
    """Записывает исходящие методы и возвращает валидные ответы Bot API."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list = []

    async def make_request(self, bot, method, timeout=None):  # type: ignore[override]
        self.calls.append(method)
        if isinstance(method, SendMessage):
            return Message(
                message_id=len(self.calls),
                date=datetime.now(UTC),
                chat=Chat(id=method.chat_id, type="private"),
                text=method.text or "",
            )
        if isinstance(method, SendChatAction):
            return True
        return True

    def sent_texts(self) -> list[str]:
        return [m.text or "" for m in self.calls if isinstance(m, SendMessage)]

    def last_reply_markup(self):
        for method in reversed(self.calls):
            if isinstance(method, SendMessage) and method.reply_markup is not None:
                return method.reply_markup
        return None

    async def close(self) -> None:
        """Required by BaseSession abstract method."""
        return

    async def stream_content(self, bot, message, content_type, **kwargs):  # type: ignore[override]
        """Required by BaseSession abstract method."""
        return


async def _make_dispatcher(engine, settings):
    from app.main import _build_dispatcher

    local = settings.model_copy(update={"bot_token": BOT_TOKEN, "free_limit": 2})
    dp, bot = _build_dispatcher(local, engine)
    session = FakeSession()
    bot.session = session  # type: ignore[assignment]
    return dp, bot, session


def _text_update(text: str, update_id: int = 1, user_id: int = 777) -> Update:
    return Update(
        update_id=update_id,
        message=Message(
            message_id=update_id,
            date=datetime.now(UTC),
            chat=Chat(id=user_id, type="private"),
            from_user=TgUser(id=user_id, is_bot=False, first_name="Тест"),
            text=text,
        ),
    )


def _photo_update(update_id: int = 1, user_id: int = 777) -> Update:
    return Update(
        update_id=update_id,
        message=Message(
            message_id=update_id,
            date=datetime.now(UTC),
            chat=Chat(id=user_id, type="private"),
            from_user=TgUser(id=user_id, is_bot=False, first_name="Тест"),
            photo=[PhotoSize(file_id="f", file_unique_id="u", width=1, height=1)],
        ),
    )


async def test_start_command_responds_and_creates_user(engine, settings):
    dp, bot, session = await _make_dispatcher(engine, settings)
    await dp.feed_update(bot, _text_update("/start"))

    texts = session.sent_texts()
    assert texts, "бот должен ответить на /start"
    assert "AI-Сотрудник" in texts[0]
    assert "Привет" in texts[0]

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        user = await UserRepo(db).get_by_tg_id(777)
        assert user is not None and user.plan == "free"


async def test_chat_flow_consumes_limit_and_replies(engine, settings):
    dp, bot, session = await _make_dispatcher(engine, settings)

    await dp.feed_update(bot, _text_update("Привет! Сколько стоит кофе?", update_id=1))
    assert any("[MOCK]" in t for t in session.sent_texts()), "в mock-режиме отвечает MockProvider"

    await dp.feed_update(bot, _text_update("А есть доставка?", update_id=2))
    await dp.feed_update(bot, _text_update("И ещё вопрос", update_id=3))  # лимит исчерпан

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        user = await UserRepo(db).get_by_tg_id(777)
        assert user is not None
        assert user.messages_used == 2  # free_limit=2: третье сообщение не списано

    assert any("Лимит сообщений" in t for t in session.sent_texts())
    assert session.last_reply_markup() is not None, "при лимите показываем кнопки апгрейда"


async def test_user_html_injection_is_escaped_in_reply(engine, settings):
    dp, bot, session = await _make_dispatcher(engine, settings)
    await dp.feed_update(bot, _text_update("<b>hack</b> & <script>alert(1)</script>"))

    joined = "\n".join(session.sent_texts())
    assert "<b>hack</b>" not in joined
    assert "<script>" not in joined
    assert "&lt;b&gt;hack&lt;/b&gt;" in joined


async def test_unknown_command_is_answered_not_sent_to_llm(engine, settings):
    dp, bot, session = await _make_dispatcher(engine, settings)
    await dp.feed_update(bot, _text_update("/nosuchcommand"))

    texts = session.sent_texts()
    assert texts and "Не знаю такой команды" in texts[0]
    assert not any("[MOCK]" in t for t in texts), "неизвестная команда не уходит в LLM"


async def test_non_text_message_gets_friendly_answer(engine, settings):
    dp, bot, session = await _make_dispatcher(engine, settings)
    await dp.feed_update(bot, _photo_update())

    texts = session.sent_texts()
    assert texts and "текстовые сообщения" in texts[0]


async def test_help_and_privacy_commands(engine, settings):
    dp, bot, session = await _make_dispatcher(engine, settings)
    await dp.feed_update(bot, _text_update("/help", update_id=1))
    await dp.feed_update(bot, _text_update("/privacy", update_id=2))

    joined = "\n".join(session.sent_texts())
    assert "/knowledge" in joined and "/buy" in joined
    assert "/forget_me" in joined and "Stars" in joined


async def test_cancel_works_without_state(engine, settings):
    dp, bot, session = await _make_dispatcher(engine, settings)
    await dp.feed_update(bot, _text_update("/cancel"))

    texts = session.sent_texts()
    assert texts and "Отменено" in texts[0]


async def test_clear_command_clears_history(engine, settings):
    dp, bot, session = await _make_dispatcher(engine, settings)
    await dp.feed_update(bot, _text_update("Привет!", update_id=1))
    await dp.feed_update(bot, _text_update("/clear", update_id=2))

    texts = session.sent_texts()
    assert any("История диалога очищена" in t for t in texts)