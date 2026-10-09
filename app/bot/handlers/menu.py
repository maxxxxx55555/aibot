"""/cancel, /privacy, reply-кнопки меню и неизвестные команды.

Роутер подключается до FSM-хэндлеров базы знаний и до чата: текст кнопок
и команды никогда не попадают в обработку как сообщения клиента.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.bot.handlers.knowledge import show_knowledge
from app.bot.helpers import safe_edit, send_authored
from app.bot.keyboards.inline import help_kb, privacy_kb
from app.bot.keyboards.reply import BTN_ASK, BTN_HELP, BTN_KNOWLEDGE, BTN_PLANS
from app.bot.texts import ASK_HINT
from app.config import Settings
from app.db.models.user import User
from app.db.repo.messages import MessageRepo

router = Router(name="menu")


@router.message(Command("clear"))
async def cmd_clear(
    message: Message, state: FSMContext, user: User, session: AsyncSession
) -> None:
    await state.clear()
    await MessageRepo(session).delete_history(user.id)
    await message.answer("🧹 <b>История диалога очищена.</b> Задайте новый вопрос!")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.CANCEL_DONE)


@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer(texts.CANCEL_DONE[:190])


@router.message(Command("privacy"))
@router.callback_query(F.data == "privacy")
async def show_privacy(event: Message | CallbackQuery, settings: Settings) -> None:
    text = texts.privacy_text(settings)
    if isinstance(event, CallbackQuery):
        await safe_edit(event.message, text, reply_markup=privacy_kb())
        await event.answer()
    else:
        await send_authored(event, text, reply_markup=privacy_kb())


@router.message(F.text == BTN_ASK)
@router.callback_query(F.data == "ask_hint")
async def ask_hint(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(event, CallbackQuery):
        await event.answer(ASK_HINT, show_alert=True)
    else:
        await event.answer(ASK_HINT)


@router.message(F.text == BTN_PLANS)
async def kb_plans(message: Message, catalog, state: FSMContext) -> None:
    from app.bot.handlers.payments import cmd_buy

    await state.clear()
    await cmd_buy(message, catalog, state)


@router.message(F.text == BTN_KNOWLEDGE)
async def kb_knowledge(message: Message, user, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    await show_knowledge(message, user, settings)


@router.message(F.text == BTN_HELP)
async def kb_help(message: Message, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    await send_authored(message, texts.help_text(settings), reply_markup=help_kb())


# Неизвестные команды (все известные перехвачены роутерами выше). Должен быть
# последним message-хэндлером команд перед catch-all чатом.
@router.message(F.text.regexp(r"^/[A-Za-z0-9_]+"))
async def unknown_command(message: Message) -> None:
    await message.answer(texts.UNKNOWN_COMMAND)