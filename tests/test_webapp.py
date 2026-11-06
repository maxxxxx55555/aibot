"""Health-сервер и WebApp REST API: /health, /game_app, /api/game/*."""

from __future__ import annotations

import pytest


@pytest.fixture
def webapp():
    return None


async def test_health_endpoint():
    from aiohttp import ClientSession

    from app import __version__
    from app.main import start_webapp

    runner = await start_webapp("127.0.0.1", 18099, None, None, None)
    try:
        async with (
            ClientSession() as http,
            http.get("http://127.0.0.1:18099/health") as resp,
        ):
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "ok"
            assert data["mode"] == "polling"
            assert data["version"] == __version__
            assert isinstance(data["uptime_s"], int) and data["uptime_s"] >= 0
    finally:
        await runner.cleanup()


async def test_health_concurrent_requests():
    """Health-эндпоинт отдаёт 200 при параллельных запросах (профиль LB)."""
    import asyncio

    from aiohttp import ClientSession

    from app.main import start_webapp

    runner = await start_webapp("127.0.0.1", 18098, None, None, None)
    try:
        async with ClientSession() as http:

            async def call() -> int:
                async with http.get("http://127.0.0.1:18098/health") as resp:
                    return resp.status

            statuses = await asyncio.gather(*[call() for _ in range(5)])
        assert statuses == [200] * 5
    finally:
        await runner.cleanup()


async def test_game_webapp_endpoints():
    """Проверка доступности WebApp /game_app и REST API симулятора."""
    from aiohttp import ClientSession

    from app.main import start_webapp

    runner = await start_webapp("127.0.0.1", 18098, None, None, None)
    try:
        async with ClientSession() as http:
            # HTML page
            async with http.get("http://127.0.0.1:18098/game_app") as resp:
                assert resp.status == 200
                text = await resp.text()
                assert "VIP Sales Simulator WebApp" in text

            # Scenarios
            async with http.get("http://127.0.0.1:18098/api/game/scenarios") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "scenarios" in data
                assert len(data["scenarios"]) == 3

            # Start game
            async with http.post(
                "http://127.0.0.1:18098/api/game/start",
                json={"scenario_id": "b2b"},
            ) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "state" in data
                assert data["state"]["scenario_id"] == "b2b"
                state = data["state"]

            # Turn
            async with http.post(
                "http://127.0.0.1:18098/api/game/turn",
                json={"state": state, "user_text": "Добрый день! Хотите демо?"},
            ) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "reply" in data
                assert not data["finished"]
                new_state = data["state"]

            # Hint
            async with http.post(
                "http://127.0.0.1:18098/api/game/hint",
                json={"state": new_state},
            ) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "hint" in data
                assert "Совет наставника" in data["hint"]
    finally:
        await runner.cleanup()