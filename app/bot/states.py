"""FSM-состояния."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class KnowledgeStates(StatesGroup):
    waiting_text = State()


class ConfirmStates(StatesGroup):
    waiting_forget = State()


class GameStates(StatesGroup):
    in_game = State()
