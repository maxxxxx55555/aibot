"""Обработчики симулятора продаж («/game»)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.helpers import safe_edit
from app.bot.keyboards.inline import get_game_keyboard, get_game_menu_keyboard
from app.bot.keyboards.reply import BTN_GAME
from app.bot.states import GameStates
from app.config import Settings
from app.services.ai.game import GameSessionState, SalesGameService

router = Router(name="game")
game_service = SalesGameService()


@router.message(Command("game"))
@router.message(F.text == BTN_GAME)
async def cmd_game(message: Message, state: FSMContext, settings: Settings) -> None:
    """Вызов стартового меню симулятора продаж."""
    await state.clear()
    kb = get_game_menu_keyboard(settings)
    await message.answer(
        "💎 <b>VIP ТРЕНАЖЁР ПРОДАЖ И КВАЛИФИКАЦИИ AI</b> 🎮\n\n"
        "Прокачайте свои навыки закрытия сделок в реальном времени!\n"
        "Выберите бизнес-сценарий и попробуйте продать решение виртуальному ЛПР:",
        reply_markup=kb,
    )


@router.callback_query(F.data == "game_menu")
async def cb_game_menu(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    """Возврат в меню выбора сценария."""
    await state.clear()
    kb = get_game_menu_keyboard(settings)
    await safe_edit(
        callback.message,
        "💎 <b>VIP ТРЕНАЖЁР ПРОДАЖ И КВАЛИФИКАЦИИ AI</b> 🎮\n\n"
        "Выберите бизнес-сценарий для тренировки:",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("game_start:"))
async def cb_game_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Старт выбранного сценария симулятора."""
    scenario_id = callback.data.split(":")[1] if callback.data and ":" in callback.data else "b2b"
    game_state, intro_text = game_service.start_game(scenario_id)

    await state.set_state(GameStates.in_game)
    await state.set_data(game_state.to_dict())

    kb = get_game_keyboard()
    await safe_edit(callback.message, intro_text, reply_markup=kb)
    await callback.answer("Симуляция началась! Удачи!")


@router.callback_query(F.data == "game_hint", GameStates.in_game)
async def cb_game_hint(callback: CallbackQuery, state: FSMContext) -> None:
    """Получение подсказки от наставника."""
    data = await state.get_data()
    game_state = GameSessionState.from_dict(data)
    hint = game_service.get_hint(game_state)
    await callback.answer(hint, show_alert=True)


@router.callback_query(F.data == "game_stop", GameStates.in_game)
async def cb_game_stop(callback: CallbackQuery, state: FSMContext) -> None:
    """Досрочный выход из симуляции."""
    await state.clear()
    await safe_edit(
        callback.message,
        "⏹ <b>Игра завершена.</b> Вы всегда можете вернуть симуляцию командой /game !",
    )
    await callback.answer("Игра остановлена")


@router.message(Command("game_stop"), GameStates.in_game)
async def cmd_game_stop(message: Message, state: FSMContext) -> None:
    """Команда остановки игры."""
    await state.clear()
    await message.answer(
        "⏹ <b>Симуляция остановлена.</b> Чтобы начать заново, введите /game"
    )


@router.message(GameStates.in_game, F.text & ~F.text.startswith("/"))
async def handle_game_turn(message: Message, state: FSMContext, settings: Settings) -> None:
    """Обработка ходов пользователя в режиме игры (пропускаем Telegram-команды)."""
    data = await state.get_data()
    game_state = GameSessionState.from_dict(data)

    user_text = message.text or ""
    new_state, reply_text, finished = game_service.process_turn(game_state, user_text)

    if finished:
        await state.clear()
        kb = get_game_menu_keyboard(settings)
        await message.answer(reply_text, reply_markup=kb)
    else:
        await state.set_data(new_state.to_dict())
        kb = get_game_keyboard()
        await message.answer(reply_text, reply_markup=kb)


@router.message(GameStates.in_game, ~F.text)
async def handle_non_text_turn(message: Message) -> None:
    """Фильтр нетекстовых сообщений в режиме игры."""
    await message.answer("⚠️ В симуляторе поддерживаются только текстовые сообщения!")
