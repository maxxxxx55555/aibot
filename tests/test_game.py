"""Автономный агентский тест-сюит и юнит-тесты для Симулятора продаж («/game»)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import User as TelegramUser

from app.bot.handlers.game import (
    cb_game_start,
    cmd_game_stop,
    handle_game_turn,
)
from app.bot.states import GameStates
from app.config import Settings
from app.services.ai.game import SCENARIOS, SalesGameService


@pytest.fixture
def game_service() -> SalesGameService:
    return SalesGameService()


def test_game_service_start_game(game_service: SalesGameService):
    state, intro = game_service.start_game("b2b")
    assert state.scenario_id == "b2b"
    assert state.turn == 1
    assert state.score == 0
    assert "B2B-клиент" in intro
    assert "Добрый день!" in intro


def test_game_service_process_turns_to_completion(game_service: SalesGameService):
    state, _ = game_service.start_game("b2b")

    # Turn 1
    state, reply1, finished1 = game_service.process_turn(state, "Добрый день! Какая цена и условия? Запишите нас на демо.")
    assert not finished1
    assert state.turn == 2
    assert state.score > 0
    assert "Раунд 2/4" in reply1

    # Turn 2
    state, _reply2, finished2 = game_service.process_turn(state, "Мы даем гарантию и поможем с настройкой. Как вас зовут?")
    assert not finished2
    assert state.turn == 3

    # Turn 3
    state, _reply3, finished3 = game_service.process_turn(state, "Для теста нужно 15 минут. Можем сделать созвон завтра?")
    assert not finished3
    assert state.turn == 4

    # Turn 4 (Final turn)
    state, reply4, finished4 = game_service.process_turn(state, "Отлично, регистрируйтесь на бесплатный тест!")
    assert finished4
    assert "Игра завершена!" in reply4
    assert "Ваш результат:" in reply4
    assert state.score >= 50


@pytest.mark.asyncio
async def test_game_handlers_flow(settings: Settings):
    storage = MemoryStorage()
    key = StorageKey(bot_id=123, chat_id=456, user_id=456)
    fsm_ctx = FSMContext(storage=storage, key=key)

    user = TelegramUser(id=456, is_bot=False, first_name="Tester")

    cb = MagicMock()
    cb.data = "game_start:b2b"
    cb.from_user = user
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()

    await cb_game_start(cb, fsm_ctx)

    current_state = await fsm_ctx.get_state()
    assert current_state == GameStates.in_game.state
    data = await fsm_ctx.get_data()
    assert data["scenario_id"] == "b2b"

    # Process turn message in state
    msg1 = MagicMock()
    msg1.text = "Здравствуйте! У нас автоматизация 24/7. Хотите тестовый доступ?"
    msg1.from_user = user
    msg1.answer = AsyncMock()

    await handle_game_turn(msg1, fsm_ctx, settings)
    msg1.answer.assert_called_once()
    answer_text = msg1.answer.call_args[0][0]
    assert "Ответ клиента" in answer_text

    # Stop game via cmd_game_stop
    stop_msg = MagicMock()
    stop_msg.text = "/game_stop"
    stop_msg.answer = AsyncMock()

    await cmd_game_stop(stop_msg, fsm_ctx)
    assert await fsm_ctx.get_state() is None


@pytest.mark.asyncio
async def test_autonomous_agent_simulator_all_scenarios(settings: Settings, game_service: SalesGameService):
    """Автономный агент-тестер: прогоняет все сценарии с разной стратегией ответов."""
    strategies = [
        ["Привет", "Цена 100", "Ок", "Пока"],  # Низкий результат
        [
            "Здравствуйте! Чем можем помочь вашему бизнесу?",
            "У вас специфическая ниша? Мы настраиваем базу знаний под ваши FAQ. Какой у вас бюджет?",
            "Наш AI работает без ошибок по вашему регламенту. Проведем демо завтра?",
            "Отлично, регистрируйтесь на бесплатный триал прям сейчас!",
        ],  # Высокий результат
    ]

    for scenario_id in SCENARIOS:
        for strat in strategies:
            state, _ = game_service.start_game(scenario_id)
            for turn_idx, user_reply in enumerate(strat, 1):
                state, reply_text, is_finished = game_service.process_turn(state, user_reply)
                if turn_idx < 4:
                    assert not is_finished
                    assert f"Раунд {turn_idx + 1}/4" in reply_text
                else:
                    assert is_finished
                    assert "Игра завершена!" in reply_text
