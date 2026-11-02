"""Контракт публичной сборки роутеров: повторяемость, изоляция, приоритет.

Регрессии, которые ловит файл (task_0006):

1. Повторные вызовы ``build_router()`` дают независимые root-роутеры, каждый
   ровно с 7 суброутерами и собственными объектами хэндлеров.
2. После сборки ни один модульный router из ``app.bot.handlers`` не получает
   parent: aiogram запрещает подключать один Router к двум родителям
   (RuntimeError «Router is already attached»), поэтому прямая вставка
   модульных роутеров ломала бы повторную сборку dispatcher.
3. Порядок суброутеров задаёт приоритет обработки:
   payments -> admin -> start -> game -> knowledge -> menu -> chat.
4. У каждого суброутера есть message-хэндлеры, а клонирование сохраняет все
   регистрации наблюдаемых событий (хэндлеры, фильтры, флаги, middlewares).
5. Повторная сборка dispatcher через ``app.main._build_dispatcher`` на новом
   engine не падает (тесты, hot-reload).
6. ``BOT_COMMANDS``: уникальные lower-case команды, валидные для Telegram,
   включая полный пользовательский набор
   (start/help/stats/buy/knowledge/privacy/cancel/forget_me).

Тесты детерминированные и офлайновые: LLM_API_KEY пуст (MockProvider),
SQLite — in-memory (StaticPool), Bot-сессии закрываются в finally.
"""

from __future__ import annotations

import re

from aiogram import Dispatcher, Router
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool

from app.bot.commands import BOT_COMMANDS, build_bot_commands
from app.bot.handlers import admin, chat, game, knowledge, menu, payments, start
from app.bot.router import build_router

EXPECTED_ORDER: tuple[str, ...] = ("payments", "admin", "start", "game", "knowledge", "menu", "chat")

MODULE_ROUTERS: dict[str, Router] = {
    "payments": payments.router,
    "admin": admin.router,
    "start": start.router,
    "game": game.router,
    "knowledge": knowledge.router,
    "menu": menu.router,
    "chat": chat.router,
}

# Формат токена как в tests/test_integration.py: Bot создаётся без сети.
BOT_TOKEN = "123456:TEST-TOKEN"

COMMAND_RE = re.compile(r"^[a-z0-9_]{1,32}$")
REQUIRED_COMMANDS = frozenset(
    {"start", "help", "game", "stats", "buy", "knowledge", "privacy", "cancel", "forget_me"}
)


def _new_engine() -> AsyncEngine:
    """In-memory SQLite (как фикстура engine): без файлов и внешней БД."""
    return create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )


def _child_message_handler_ids(router: Router) -> set[int]:
    return {
        id(handler)
        for child in router.sub_routers
        for handler in child.observers["message"].handlers
    }


def test_build_router_returns_independent_roots_with_seven_children():
    root_a = build_router()
    root_b = build_router()

    assert isinstance(root_a, Router) and isinstance(root_b, Router)
    assert root_a is not root_b, "каждый вызов build_router() обязан создавать новый root"
    assert root_a.parent_router is None and root_b.parent_router is None
    assert len(root_a.sub_routers) == 7, "root обязан содержать 7 суброутеров"
    assert len(root_b.sub_routers) == 7, "root обязан содержать 7 суброутеров"

    # Деревья не переиспользуют Router-объекты: aiogram не даёт привязать один
    # Router к двум родителям, поэтому повторная сборка ломалась бы.
    assert {id(r) for r in root_a.sub_routers}.isdisjoint({id(r) for r in root_b.sub_routers})
    assert all(child.parent_router is root_a for child in root_a.sub_routers)
    assert all(child.parent_router is root_b for child in root_b.sub_routers)

    # Хэндлеры — тоже независимые объекты (клонирование, а не повторное использование).
    handlers_a = _child_message_handler_ids(root_a)
    handlers_b = _child_message_handler_ids(root_b)
    assert handlers_a and handlers_b
    assert handlers_a.isdisjoint(handlers_b)


def test_module_routers_stay_detached_after_build():
    build_router()
    build_router()

    for name, module_router in MODULE_ROUTERS.items():
        assert module_router.parent_router is None, (
            f"router app.bot.handlers.{name} получил parent после build_router(); "
            "повторная сборка dispatcher упадёт с RuntimeError «Router is already attached»"
        )

    root = build_router()
    assert {id(r) for r in root.sub_routers}.isdisjoint(
        {id(r) for r in MODULE_ROUTERS.values()}
    ), "build_router() подключил модульный router напрямую вместо независимой копии"


def test_sub_router_priority_order():
    root = build_router()

    assert [r.name for r in root.sub_routers] == list(EXPECTED_ORDER)
    assert {r.name for r in root.sub_routers} == set(MODULE_ROUTERS)


def test_every_sub_router_has_message_handlers_and_clone_is_faithful():
    root = build_router()
    children = {child.name: child for child in root.sub_routers}

    for name, child in children.items():
        message_handlers = child.observers["message"].handlers
        assert message_handlers, f"у суброутера {name!r} нет message-хэндлеров"
        assert all(callable(handler.callback) for handler in message_handlers)

    # Клонирование переносит все регистрации каждого наблюдаемого события.
    for name, module_router in MODULE_ROUTERS.items():
        child = children[name]
        assert set(child.observers) == set(module_router.observers)
        for event_name, module_observer in module_router.observers.items():
            child_observer = child.observers[event_name]
            assert len(child_observer.handlers) == len(module_observer.handlers), (
                f"{name}:{event_name}: хэндлеры потеряны при клонировании"
            )
            assert [len(h.filters or []) for h in child_observer.handlers] == [
                len(h.filters or []) for h in module_observer.handlers
            ], f"{name}:{event_name}: фильтры потеряны при клонировании"
            assert [h.flags for h in child_observer.handlers] == [
                h.flags for h in module_observer.handlers
            ], f"{name}:{event_name}: flags потеряны при клонировании"
            assert len(list(child_observer.middleware)) == len(
                list(module_observer.middleware)
            ), f"{name}:{event_name}: middlewares потеряны при клонировании"
            assert len(list(child_observer.outer_middleware)) == len(
                list(module_observer.outer_middleware)
            ), f"{name}:{event_name}: outer middlewares потеряны при клонировании"


async def test_build_dispatcher_repeatable_with_new_engine(settings):
    from app.main import _build_dispatcher

    local = settings.model_copy(update={"bot_token": BOT_TOKEN})
    engines = [_new_engine(), _new_engine()]
    bots = []
    try:
        dispatchers = []
        for engine in engines:
            dp, bot = _build_dispatcher(local, engine)
            dispatchers.append(dp)
            bots.append(bot)

        assert dispatchers[0] is not dispatchers[1], "каждая сборка — свой Dispatcher"
        for dp in dispatchers:
            assert isinstance(dp, Dispatcher)
            assert dp["settings"] is local
            assert len(dp.sub_routers) == 1, "root подключается к dispatcher ровно один раз"
            assert [r.name for r in dp.sub_routers[0].sub_routers] == list(EXPECTED_ORDER)
            for observer_name in ("message", "callback_query", "pre_checkout_query"):
                observer = dp.observers[observer_name]
                assert len(list(observer.middleware)) == 3, (
                    f"{observer_name}: DbSession/User/Throttling middlewares потеряны"
                )
            assert len(dp.errors.handlers) == 1, "error-handler обязан быть зарегистрирован"

        # Повторная сборка не привязала модульные роутеры к диспетчерам.
        for name, module_router in MODULE_ROUTERS.items():
            assert module_router.parent_router is None, (
                f"app.bot.handlers.{name}.router получил parent после _build_dispatcher"
            )
    finally:
        for bot in bots:
            await bot.session.close()
        for engine in engines:
            await engine.dispose()


def test_bot_commands_contract_is_unique_lowercase_and_complete():
    assert isinstance(BOT_COMMANDS, tuple) and BOT_COMMANDS
    names = [name for name, _description in BOT_COMMANDS]

    assert len(names) == len(set(names)), "команды меню Telegram обязаны быть уникальны"
    for name in names:
        assert name == name.lower(), f"команда {name!r} должна быть в нижнем регистре"
        assert COMMAND_RE.fullmatch(name), f"команда {name!r} недопустима для Telegram"
    missing = REQUIRED_COMMANDS - set(names)
    assert not missing, f"меню команд потеряло: {sorted(missing)}"
    assert all(description.strip() for _name, description in BOT_COMMANDS), (
        "у каждой команды должно быть непустое описание"
    )


def test_build_bot_commands_mirrors_bot_commands():
    commands = build_bot_commands()

    assert [command.command for command in commands] == [name for name, _ in BOT_COMMANDS]
    assert all(command.description for command in commands)
    assert [command.command for command in commands[:2]] == ["start", "help"]
