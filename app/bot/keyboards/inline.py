"""Inline-клавиатуры: меню, выбор тарифа, апсейл, игра."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import Settings
from app.services.billing.plans import PlanCatalog


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🎮 Тренажёр продаж", callback_data="game_menu")
    kb.button(text="⭐️ Тарифы", callback_data="plans")
    kb.button(text="📚 База знаний", callback_data="knowledge")
    kb.button(text="ℹ️ Помощь", callback_data="help")
    kb.button(text="🔐 Приватность", callback_data="privacy")
    kb.adjust(1, 2, 2)
    return kb.as_markup()


def plans_kb(catalog: PlanCatalog) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for plan in catalog.paid():
        kb.button(
            text=f"⭐️ {plan.title} — {plan.price_stars} Stars",
            callback_data=f"buy:{plan.id}",
        )
    kb.button(text="⬅️ Назад", callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def upsell_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 Перейти на PRO", callback_data="plans")
    kb.button(text="⬅️ В меню", callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def help_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Как задать вопрос", callback_data="ask_hint")
    kb.button(text="🎮 Тренажёр продаж", callback_data="game_menu")
    kb.button(text="📚 База знаний", callback_data="knowledge")
    kb.button(text="⭐️ Тарифы", callback_data="plans")
    kb.button(text="🔐 Приватность", callback_data="privacy")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def privacy_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Удалить все данные", callback_data="forget_me")
    kb.button(text="⬅️ В меню", callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def knowledge_kb(can_upload: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if can_upload:
        kb.button(text="➕ Добавить знания", callback_data="knowledge_add")
    else:
        kb.button(text="🚀 Подключить в PRO", callback_data="plans")
    kb.button(text="🗑 Забыть обо мне", callback_data="forget_me")
    kb.button(text="⬅️ Назад", callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def forget_confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, удалить всё", callback_data="forget_confirm")
    kb.button(text="❌ Отмена", callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def get_game_menu_keyboard(settings: Settings | None = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🏢 B2B Enterprise SaaS", callback_data="game_start:b2b")
    kb.button(text="🏠 Сфера услуг (Недвижимость)", callback_data="game_start:services")
    kb.button(text="🛒 E-commerce Ритейл", callback_data="game_start:ecommerce")
    if settings and settings.webapp_url:
        kb.button(text="📱 Открыть WebApp Игру", web_app=WebAppInfo(url=settings.webapp_url))
    kb.button(text="⬅️ В меню", callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def get_game_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💡 Подсказка наставника", callback_data="game_hint")
    kb.button(text="⏹ Завершить симуляцию", callback_data="game_stop")
    kb.adjust(1)
    return kb.as_markup()
