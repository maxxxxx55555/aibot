"""Reply-клавиатура быстрых действий (показывается после /start).

Лейблы кнопок — константы: хэндлеры и FSM-фильтры используют их, чтобы
текст кнопки никогда не «утёк» в обработку как обычное сообщение.
"""

from __future__ import annotations

from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

BTN_ASK = "💬 Задать вопрос"
BTN_GAME = "🎮 Игровой симулятор"
BTN_PLANS = "⭐️ Тарифы"
BTN_KNOWLEDGE = "📚 База знаний"
BTN_HELP = "ℹ️ Помощь"

BUTTON_LABELS: frozenset[str] = frozenset({BTN_ASK, BTN_GAME, BTN_PLANS, BTN_KNOWLEDGE, BTN_HELP})


def quick_actions() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text=BTN_ASK)
    kb.button(text=BTN_GAME)
    kb.button(text=BTN_PLANS)
    kb.button(text=BTN_KNOWLEDGE)
    kb.button(text=BTN_HELP)
    kb.adjust(2, 3)
    return kb.as_markup(resize_keyboard=True)