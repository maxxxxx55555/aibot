"""Reply-клавиатура главных быстрых действий."""

from __future__ import annotations

from aiogram.types import ReplyKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from app.config import Settings

BTN_ASK = "💬 Задать вопрос"
BTN_GAME = "🎮 Тренажёр продаж"
BTN_PLANS = "⭐️ Тарифы"
BTN_KNOWLEDGE = "📚 База знаний"
BTN_HELP = "ℹ️ Помощь"

BUTTON_LABELS: frozenset[str] = frozenset({BTN_ASK, BTN_GAME, BTN_PLANS, BTN_KNOWLEDGE, BTN_HELP})


def quick_actions(settings: Settings | None = None) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text=BTN_ASK)
    kb.button(text=BTN_GAME)
    if settings and settings.webapp_url:
        kb.button(text="📱 WebApp Игра", web_app=WebAppInfo(url=settings.webapp_url))
    kb.button(text=BTN_PLANS)
    kb.button(text=BTN_KNOWLEDGE)
    kb.button(text=BTN_HELP)
    kb.adjust(2, 2, 2)
    return kb.as_markup(resize_keyboard=True)