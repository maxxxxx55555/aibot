"""/game — Симулятор продаж (игровой тренажёр квалификации лидов)."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot import texts
from app.bot.helpers import safe_edit, send_authored
from app.bot.keyboards.inline import game_end_kb, game_menu_kb, game_stop_kb, main_menu
from app.bot.keyboards.reply import BTN_GAME, BUTTON_LABELS
from app.bot.states import GameStates
from app.config import Settings
from app.services.ai.game import GameSessionState, SalesGameService

router = Router(name="game")
logger = logging.getLogger(__name__)

game_service = SalesGameService()


@router.message(Command("game"))
@router.message(F.text == BTN_GAME)
async def cmd_game(event: Message, state: FSMContext) -> None:
    await state.clear()
    kb = game_menu_kb()
    intro_text = (
        "🎮 <b>Игровой симулятор продаж «AI-Сотрудник»</b>\n\n"
        "Проверьте свои навыки квалификации лидов или посмотрите, как бот общается с клиентами!\n"
        "Вам предстоит диалог с виртуальным клиентом на 4 раунда.\n\n"
        "Выберите сценарий для старта игры:"
    )
    await send_authored(event, intro_text, reply_markup=kb)


@router.callback_query(F.data == "game_menu")
async def cb_game_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    kb = game_menu_kb()
    intro_text = (
        "🎮 <b>Игровой симулятор продаж «AI-Сотрудник»</b>\n\n"
        "Выберите сценарий для старта игры:"
    )
    if callback.message:
        await safe_edit(callback.message, intro_text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("game_start:"))
async def cb_game_start(callback: CallbackQuery, state: FSMContext) -> None:
    scenario_id = callback.data.split(":")[1] if callback.data and ":" in callback.data else "b2b"
    game_state, intro = game_service.start_game(scenario_id)
    await state.set_state(GameStates.in_game)
    await state.set_data(game_state.to_dict())
    if callback.message:
        await safe_edit(callback.message, intro, reply_markup=game_stop_kb())
    await callback.answer()


@router.callback_query(F.data == "game_stop")
async def cb_game_stop(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    text = "🎮 Игра остановлена. В любой момент вы можете начать новую игру командой /game !"
    if callback.message:
        await safe_edit(callback.message, text, reply_markup=main_menu())
    await callback.answer()


@router.message(Command("game_stop"), StateFilter(GameStates.in_game))
async def cmd_game_stop(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("🎮 Игра остановлена. Запустить снова: /game")


@router.message(
    StateFilter(GameStates.in_game),
    F.text,
    ~F.text.startswith("/"),
    ~F.text.in_(BUTTON_LABELS),
)
async def handle_game_turn(message: Message, state: FSMContext, settings: Settings) -> None:
    assert message.text is not None
    text = message.text.strip()

    if len(text) > settings.max_message_len:
        await message.answer(texts.message_too_long(settings.max_message_len))
        return

    data = await state.get_data()
    game_session = GameSessionState.from_dict(data)

    game_session, reply_text, is_finished = game_service.process_turn(game_session, text)

    if is_finished:
        await state.clear()
        await message.answer(reply_text, reply_markup=game_end_kb())
    else:
        await state.set_data(game_session.to_dict())
        await message.answer(reply_text, reply_markup=game_stop_kb())


@router.message(StateFilter(GameStates.in_game))
async def handle_non_text_turn(message: Message) -> None:
    await message.answer(
        "🎮 В симуляторе поддерживаются только текстовые сообщения.\n"
        "Напишите ваш ответ текстом или нажмите /game_stop для выхода."
    )
