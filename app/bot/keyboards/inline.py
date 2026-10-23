"""Inline-клавиатуры: меню, выбор тарифа, апсейл, тренажёр продаж."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

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


def game_menu_kb(webapp_url: str | None = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🏢 B2B SaaS (Автоматизация)", callback_data="game_start:b2b")
    kb.button(text="🏥 Клиника (Сфера услуг)", callback_data="game_start:services")
    kb.button(text="🛒 E-commerce (Ритейл)", callback_data="game_start:ecommerce")
    if webapp_url:
        kb.button(text="📱 Открыть WebApp версию", web_app=WebAppInfo(url=webapp_url))
    kb.button(text="⬅️ В меню", callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def game_stop_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💡 Подсказка AI-наставника", callback_data="game_hint")
    kb.button(text="🛑 Завершить игру", callback_data="game_stop")
    kb.adjust(1)
    return kb.as_markup()


def game_end_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Играть снова", callback_data="game_menu")
    kb.button(text="📚 Загрузить базу знаний", callback_data="knowledge")
    kb.button(text="⬅️ В меню", callback_data="menu")
    kb.adjust(1)
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
    kb.button(text="📚 База знаний", callback_data="knowledge")
    kb.button(text="⭐️ Тарифы", callback_data="plans")
    kb.button(text="🔐 Приватность", callback_data="privacy")
    kb.adjust(2, 2)
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