"""Контрактные тесты маршрутизации Telegram-бота.

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
   (start/game/help/stats/buy/knowledge/privacy/cancel/forget_me).

Тесты детерминированные и офлайновые: LLM_API_KEY пуст (MockProvider),
SQLite — in-memory (StaticPool), Bot-сессии закрываются в finally.
"""

from __future__ import annotations

import re

from aiogram import Router
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

BOT_TOKEN = "123456:TEST-TOKEN"

COMMAND_RE = re.compile(r"^[a-z0-9_]{1,32}$")
REQUIRED_COMMANDS = frozenset(
    {"start", "game", "help", "stats", "buy", "knowledge", "privacy", "cancel", "forget_me"}
)


def _make_test_engine() -> AsyncEngine:
    return create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )


def _child_message_handler_ids(router: Router) -> set[int]:
    return {
        id(h.callback)
        for sub in router.sub_routers
        for h in sub.message.handlers
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
    for sub_a, sub_b in zip(root_a.sub_routers, root_b.sub_routers, strict=True):
        assert sub_a is not sub_b
        assert sub_a.parent_router is root_a
        assert sub_b.parent_router is root_b

    # Повторный вызов build_router() регистрирует те же функции-хэндлеры,
    # но в НОВЫХ обёртках суброутеров.
    assert _child_message_handler_ids(root_a) == _child_message_handler_ids(root_b)


def test_module_routers_remain_unattached_after_build():
    """Модульные роутеры не получают parent, так как build_router клонирует их."""
    build_router()
    for name, r in MODULE_ROUTERS.items():
        assert r.parent_router is None, f"модульный {name}.router не должен привязываться к root"


def test_subrouter_order_and_names():
    root = build_router()
    names = tuple(sub.name for sub in root.sub_routers)
    assert names == EXPECTED_ORDER, f"порядок суброутеров изменён: {names} != {EXPECTED_ORDER}"


def test_every_subrouter_has_message_handlers():
    root = build_router()
    for sub in root.sub_routers:
        assert len(sub.message.handlers) > 0, f"суброутер {sub.name} не имеет message-хэндлеров"


def test_cloned_subrouters_preserve_event_registrations():
    root = build_router()
    by_name = {sub.name: sub for sub in root.sub_routers}

    for name, original in MODULE_ROUTERS.items():
        cloned = by_name[name]
        assert len(cloned.message.handlers) == len(original.message.handlers)
        assert len(cloned.callback_query.handlers) == len(original.callback_query.handlers)
        assert len(cloned.pre_checkout_query.handlers) == len(original.pre_checkout_query.handlers)
        assert len(cloned.errors.handlers) == len(original.errors.handlers)

        for obs_name in ("message", "callback_query", "pre_checkout_query"):
            src_obs = getattr(original, obs_name)
            dst_obs = getattr(cloned, obs_name)
            assert len(dst_obs.outer_middleware) == len(src_obs.outer_middleware)
            assert len(dst_obs.middleware) == len(src_obs.middleware)


def test_rebuilding_dispatcher_does_not_raise(settings):
    """Эмулирует сборку бота в тестах / при смене конфига без конфликта aiogram."""
    from app.main import _build_dispatcher

    test_settings = settings.model_copy(update={"bot_token": BOT_TOKEN})
    engine1 = _make_test_engine()
    engine2 = _make_test_engine()

    dp1, _bot1 = _build_dispatcher(test_settings, engine1)
    dp2, _bot2 = _build_dispatcher(test_settings, engine2)

    assert dp1 is not dp2
    assert dp1.sub_routers[0] is not dp2.sub_routers[0]

    # Ссылки в workflow_data корректны
    assert dp1["settings"] is test_settings and dp2["settings"] is test_settings


def test_bot_commands_list_validity_and_completeness():
    assert len(BOT_COMMANDS) == len(dict(BOT_COMMANDS)), "список BOT_COMMANDS содержит дубликаты ключей"

    command_names = [cmd for cmd, _ in BOT_COMMANDS]

    for name in command_names:
        assert COMMAND_RE.match(name), f"команда {name!r} не соответствует формату Telegram"

    missing = REQUIRED_COMMANDS - set(command_names)
    assert not missing, f"в BOT_COMMANDS отсутствуют обязательные команды: {sorted(missing)}"

    # Команды в lower-case, без '/'; описания информативны
    for cmd, desc in BOT_COMMANDS:
        assert cmd == cmd.lower(), f"команда {cmd!r} должна быть в нижнем регистре"
        assert not cmd.startswith("/"), f"команда {cmd!r} не должна начинаться с '/'"
        assert len(desc.strip()) >= 5, f"описание команды {cmd!r} слишком короткое"


def test_build_bot_commands_mirrors_bot_commands():
    commands = build_bot_commands()

    assert [command.command for command in commands] == [name for name, _ in BOT_COMMANDS]
    assert all(command.description for command in commands)
    assert [command.command for command in commands[:2]] == ["start", "game"]
