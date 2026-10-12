"""/knowledge — база знаний (RAG) для тарифов PRO/Business.

Источники знаний: текст сообщением или файл .txt/.md. Во время FSM-ожидания
текста команды и кнопки меню не попадают в базу (обрабатываются другими роутерами
либо явно отвергаются здесь).
"""

from __future__ import annotations

import logging
from io import BytesIO

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.bot.helpers import safe_edit, send_authored
from app.bot.keyboards.inline import knowledge_kb
from app.bot.keyboards.reply import BUTTON_LABELS
from app.bot.states import KnowledgeStates
from app.config import Settings
from app.db.models.user import User
from app.db.repo.knowledge import KnowledgeRepo
from app.services.ai.rag import RagService

router = Router(name="knowledge")
logger = logging.getLogger(__name__)

MAX_KNOWLEDGE_CHARS = 100_000  # символов в одном тексте базы знаний
MAX_DOCUMENT_BYTES = 256 * 1024  # размер загружаемого файла
_ALLOWED_EXTENSIONS = (".txt", ".md")


def _is_knowledge_file(message: Message) -> bool:
    document = message.document
    if document is None:
        return False
    filename = (document.file_name or "").lower()
    return document.mime_type == "text/plain" or filename.endswith(_ALLOWED_EXTENSIONS)


async def show_knowledge(
    target: Message, user: User, settings: Settings, chunks: int = 0
) -> None:
    """Экран базы знаний — общий для команды, кнопок и callback."""
    text = texts.knowledge_intro(
        user.plan != "free", settings.max_message_len, MAX_DOCUMENT_BYTES // 1024
    )
    if user.plan != "free":
        text += f"\n\nЗагружено фрагментов: <b>{chunks}</b>"
    await send_authored(
        target,
        text,
        reply_markup=knowledge_kb(user.plan != "free"),
    )


@router.message(Command("knowledge"))
async def cmd_knowledge(
    message: Message, user: User, session: AsyncSession, settings: Settings
) -> None:
    chunks = await KnowledgeRepo(session).count_for_owner(user.id)
    await show_knowledge(message, user, settings, chunks)


@router.callback_query(F.data == "knowledge")
async def cb_knowledge(
    callback: CallbackQuery, user: User, session: AsyncSession, settings: Settings
) -> None:
    text = texts.knowledge_intro(
        user.plan != "free", settings.max_message_len, MAX_DOCUMENT_BYTES // 1024
    )
    if user.plan != "free":
        chunks = await KnowledgeRepo(session).count_for_owner(user.id)
        text += f"\n\nЗагружено фрагментов: <b>{chunks}</b>"
    await safe_edit(callback.message, text, reply_markup=knowledge_kb(user.plan != "free"))
    await callback.answer()


@router.callback_query(F.data == "knowledge_add")
async def cb_knowledge_add(
    callback: CallbackQuery, state: FSMContext, user: User, settings: Settings
) -> None:
    if user.plan == "free":
        await callback.answer(texts.NEED_PLAN, show_alert=True)
        return
    await state.set_state(KnowledgeStates.waiting_text)
    await safe_edit(
        callback.message,
        "📚 Отправьте текст базы знаний одним сообщением "
        f"(до {settings.max_message_len} символов) или файлом .txt/.md.\n\n"
        "<i>Например: «Мы кофейня на Ленина 5. Работаем 8:00–22:00. Капучино — 250 ₽…»</i>\n\n"
        "Для отмены: /cancel",
    )
    await callback.answer()


@router.message(
    KnowledgeStates.waiting_text,
    F.text,
    ~F.text.in_(BUTTON_LABELS),
    ~F.text.startswith("/"),
)
async def save_knowledge(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    rag: RagService,
    settings: Settings,
) -> None:
    assert message.text is not None
    text = message.text.strip()

    if len(text) > settings.max_message_len:
        await message.answer(texts.message_too_long(settings.max_message_len))
        return

    added = await rag.add_text(session, user.id, text)
    if added == 0:
        await message.answer("🤷 Не нашёл в сообщении текста для базы знаний. Попробуйте ещё раз или /cancel")
        return
    await state.clear()
    await message.answer(texts.knowledge_saved(added))


@router.message(KnowledgeStates.waiting_text, F.document)
async def save_knowledge_file(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    rag: RagService,
) -> None:
    document = message.document
    assert document is not None
    filename = document.file_name or "knowledge.txt"

    if not _is_knowledge_file(message):
        await message.answer("✋ Поддерживаются только текстовые файлы .txt или .md.")
        return
    if (document.file_size or 0) > MAX_DOCUMENT_BYTES:
        await message.answer(
            f"✋ Файл слишком большой (максимум {MAX_DOCUMENT_BYTES // 1024} КБ). "
            "Разбейте его на части."
        )
        return

    buffer = BytesIO()
    try:
        await message.bot.download(document, destination=buffer)
    except Exception:  # noqa: BLE001 — сеть/Telegram: не роняем апдейт
        logger.warning("Не удалось скачать документ user_id=%s", user.id)
        await message.answer("❌ Не удалось скачать файл, попробуйте ещё раз.")
        return
    content = buffer.getvalue().decode("utf-8", errors="replace").strip()
    if not content:
        await message.answer("🤷 Файл пустой — нечего добавить в базу знаний.")
        return
    if len(content) > MAX_KNOWLEDGE_CHARS:
        await message.answer(
            f"✋ В файле больше {MAX_KNOWLEDGE_CHARS // 1000} тыс. символов. "
            "Разделите его на несколько файлов."
        )
        return

    added = await rag.add_text(session, user.id, content)
    await state.clear()
    logger.info("Knowledge file uploaded by user_id=%s: chunks=%s", user.id, added)
    await message.answer(texts.knowledge_file_saved(added, filename))


@router.message(KnowledgeStates.waiting_text)
async def knowledge_wrong_type(message: Message) -> None:
    await message.answer(
        "✋ Отправьте текст сообщением или файлом .txt/.md. Для отмены: /cancel"
    )