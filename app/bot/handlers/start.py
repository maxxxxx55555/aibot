"""/start, /help, /stats — онбординг, справка и статус лимитов."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.bot.helpers import safe_edit, send_authored
from app.bot.keyboards.inline import forget_confirm_kb, help_kb, main_menu
from app.bot.keyboards.reply import quick_actions
from app.config import Settings
from app.db.models.user import User
from app.db.repo.knowledge import KnowledgeRepo
from app.db.repo.messages import MessageRepo
from app.db.repo.payments import PaymentRepo
from app.services.ai.rag import RagService
from app.services.billing.plans import PlanCatalog

router = Router(name="start")
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    command: CommandObject,
    user: User,
    catalog: PlanCatalog,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await state.clear()
    await session.refresh(user)  # актуальный лимит после возможного ленивого сброса
    name = message.from_user.first_name if message.from_user else "друг"
    if command.args:
        # Deeplink-метки (`?start=camp1`) — бесплатная аналитика источников трафика
        logger.info("Старт по deeplink: payload=%r user_id=%s", command.args[:64], user.id)
    await send_authored(
        message,
        texts.welcome(name, catalog),
        reply_markup=quick_actions(),
    )


@router.message(Command("help"))
@router.callback_query(F.data == "help")
async def cmd_help(event: Message | CallbackQuery, settings: Settings) -> None:
    text = texts.help_text(settings)
    if isinstance(event, CallbackQuery):
        await safe_edit(event.message, text, reply_markup=help_kb())
        await event.answer()
    else:
        await send_authored(event, text, reply_markup=help_kb())


@router.message(Command("stats"))
async def cmd_stats(
    message: Message,
    user: User,
    catalog: PlanCatalog,
    session: AsyncSession,
) -> None:
    await session.refresh(user)
    limit = catalog.limit_for(user.plan)
    remaining = max(limit - user.messages_used, 0)
    plan = catalog.get(user.plan)
    chunks = await KnowledgeRepo(session).count_for_owner(user.id)
    percent = round(user.messages_used / limit * 100) if limit else 0

    lines = [
        "📊 <b>Ваш статус</b>",
        f"Тариф: <b>{plan.title if plan else user.plan}</b>",
        f"Лимит: {user.messages_used}/{limit} сообщений использовано ({percent}%)",
        f"Осталось: <b>{remaining}</b>",
        f"Обновление лимита: {user.period_reset_at.strftime('%d.%m.%Y %H:%M UTC')}",
    ]
    if user.plan != "free":
        lines.append(f"База знаний: {chunks} фрагментов")
    lines.append("")
    lines.append("Апгрейд и продление: /buy" if user.plan != "free" else "Апгрейд: /buy")
    await message.answer("\n".join(lines))


@router.callback_query(F.data == "menu")
async def cb_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit(callback.message, "Главное меню 👇", reply_markup=main_menu())
    await callback.answer()


@router.message(Command("forget_me"))
async def cmd_forget_me(message: Message, state: FSMContext) -> None:
    """Командный вход в удаление данных: тот же confirm-экран, что и по кнопке."""
    await state.clear()
    await message.answer(
        "⚠️ Удалить <b>все</b> ваши данные: профиль, историю диалогов, базу знаний?\n"
        "Действие необратимо.",
        reply_markup=forget_confirm_kb(),
    )


@router.callback_query(F.data == "forget_me")
async def cb_forget(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit(
        callback.message,
        "⚠️ Удалить <b>все</b> ваши данные: профиль, историю диалогов, базу знаний?\n"
        "Действие необратимо.",
        reply_markup=forget_confirm_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "forget_confirm")
async def cb_forget_confirm(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    rag: RagService | None = None,
) -> None:
    user_id = user.id
    # Платежи ссылаются на пользователя через RESTRICT: сначала удаляем их,
    # иначе удаление профиля платящего пользователя упадёт на PostgreSQL.
    await PaymentRepo(session).delete_for_user(user_id)
    await MessageRepo(session).delete_history(user_id)
    if rag is not None:
        await rag.forget_owner(session, user_id)  # SQLite и/или ChromaDB
    else:
        await KnowledgeRepo(session).delete_for_owner(user_id)
    await session.delete(user)
    await session.flush()
    logger.info("Пользователь удалил все данные: user_id=%s", user_id)
    await safe_edit(callback.message, "🗑 Все ваши данные удалены. Введите /start, чтобы начать заново.")
    await callback.answer("Данные удалены")