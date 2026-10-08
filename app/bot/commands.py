"""Список команд бота — синхронизируется с Telegram при старте (setMyCommands).

Пользователь всегда видит актуальное меню команд (кнопка «Меню» в чате),
как у нативных ботов. Админ-команды намеренно не публикуются.
"""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import BotCommand

logger = logging.getLogger(__name__)

BOT_COMMANDS: tuple[tuple[str, str], ...] = (
    ("start", "Начать работу"),
    ("help", "Справка и возможности"),
    ("game", "🎮 Симулятор продаж"),
    ("stats", "Мой тариф и остаток лимита"),
    ("buy", "Тарифы и оплата (Stars)"),
    ("knowledge", "База знаний (PRO/Business)"),
    ("privacy", "Как хранятся данные"),
    ("cancel", "Отменить текущее действие"),
    ("forget_me", "Удалить все мои данные"),
)


def build_bot_commands() -> list[BotCommand]:
    return [BotCommand(command=name, description=desc) for name, desc in BOT_COMMANDS]


async def register_commands(bot: Bot) -> bool:
    """Публикует меню команд. Не роняет запуск при сетевой ошибке."""
    try:
        await bot.set_my_commands(build_bot_commands())
        logger.info("Меню команд синхронизировано (%s шт.)", len(BOT_COMMANDS))
        return True
    except Exception as exc:  # noqa: BLE001 — офлайн-запуск/лимиты Telegram не критичны
        logger.warning("Не удалось синхронизировать меню команд: %s", exc)
        return False
