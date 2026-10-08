"""Роутер: агрегация хэндлеров в порядке приоритета.

Порядок важен: платежи -> админка -> команды -> игра -> база знаний (FSM) -> меню -> чат.
Специфичные фильтры всегда раньше общих.
"""

from __future__ import annotations

from aiogram import Router


def _clone_router(source: Router, name: str) -> Router:
    """Создаёт независимую копию роутера только через публичный API aiogram.

    Aiogram запрещает подключать один Router к двум родителям, поэтому при
    повторной сборке dispatcher (тесты, hot-reload) регистрации переносятся в
    новый Router: для каждого хэндлера заново вызывается observer.register()
    с исходными фильтрами. Приватные поля (`_handler`, `_parent_router`) не
    используются.
    """
    target = Router(name=name)
    for event_name, source_observer in source.observers.items():
        target_observer = target.observers[event_name]
        for middleware in source_observer.middleware:
            target_observer.middleware(middleware)
        for middleware in source_observer.outer_middleware:
            target_observer.outer_middleware(middleware)
        for handler in source_observer.handlers:
            filters = [
                filter_object.magic if filter_object.magic is not None else filter_object.callback
                for filter_object in (handler.filters or [])
            ]
            target_observer.register(handler.callback, *filters, flags=dict(handler.flags))
    return target


def build_router() -> Router:
    """Создаёт новый root-роутер с хэндлерами в порядке приоритета."""
    router = Router(name="root")
    from app.bot.handlers import admin, chat, game, knowledge, menu, payments, start

    router.include_router(_clone_router(payments.router, "payments"))
    router.include_router(_clone_router(admin.router, "admin"))
    router.include_router(_clone_router(start.router, "start"))
    router.include_router(_clone_router(game.router, "game"))
    router.include_router(_clone_router(knowledge.router, "knowledge"))
    router.include_router(_clone_router(menu.router, "menu"))
    router.include_router(_clone_router(chat.router, "chat"))
    return router
