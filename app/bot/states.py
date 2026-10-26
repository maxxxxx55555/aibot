"""FSM состояния Telegram-бота."""

from aiogram.fsm.state import State, StatesGroup


class KnowledgeStates(StatesGroup):
    waiting_for_text = State()


class GameStates(StatesGroup):
    in_game = State()
