"""Health-сервер и WebApp/Game REST API: /health, /game_app, /api/game/*."""

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


async def test_game_webapp_and_api_endpoints():
    """Проверка работы /game_app и REST API симулятора продаж."""
    from aiohttp import ClientSession

    from app.main import start_webapp

    runner = await start_webapp("127.0.0.1", 18097, None, None, None)
    try:
        async with ClientSession() as http:
            # 1. GET /game_app
            async with http.get("http://127.0.0.1:18097/game_app") as resp:
                assert resp.status == 200
                html = await resp.text()
                assert "VIP Sales Simulator" in html

            # 2. GET /api/game/scenarios
            async with http.get("http://127.0.0.1:18097/api/game/scenarios") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "scenarios" in data
                assert "b2b" in data["scenarios"]

            # 3. POST /api/game/start
            async with http.post(
                "http://127.0.0.1:18097/api/game/start",
                json={"scenario_id": "b2b"},
            ) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "state" in data
                assert "intro" in data
                game_state = data["state"]

            # 4. POST /api/game/hint
            async with http.post(
                "http://127.0.0.1:18097/api/game/hint",
                json={"state": game_state},
            ) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "hint" in data
                assert "Совет наставника" in data["hint"]

            # 5. POST /api/game/turn
            async with http.post(
                "http://127.0.0.1:18097/api/game/turn",
                json={"state": game_state, "user_text": "Здравствуйте! Мы проведем бесплатный тест."},
            ) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "reply" in data
                assert data["finished"] is False
    finally:
        await runner.cleanup()
