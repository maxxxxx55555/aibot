"""Health-сервер и WebApp API: /health, /game_app и /api/game/*."""

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


async def test_game_webapp_endpoints():
    """Проверка работы интерфейса WebApp и REST API симулятора."""
    from aiohttp import ClientSession

    from app.main import start_webapp

    runner = await start_webapp("127.0.0.1", 18097, None, None, None)
    try:
        async with ClientSession() as http:
            # 1. /game_app (HTML page)
            async with http.get("http://127.0.0.1:18097/game_app") as resp:
                assert resp.status == 200
                html = await resp.text()
                assert "VIP Sales Simulator WebApp" in html

            # 2. /api/game/scenarios
            async with http.get("http://127.0.0.1:18097/api/game/scenarios") as resp:
                assert resp.status == 200
                scenarios_data = await resp.json()
                assert "scenarios" in scenarios_data
                assert len(scenarios_data["scenarios"]) >= 3

            # 3. /api/game/start
            async with http.post(
                "http://127.0.0.1:18097/api/game/start", json={"scenario_id": "b2b"}
            ) as resp:
                assert resp.status == 200
                start_data = await resp.json()
                assert "state" in start_data
                assert "intro" in start_data

            state = start_data["state"]

            # 4. /api/game/turn
            async with http.post(
                "http://127.0.0.1:18097/api/game/turn",
                json={"state": state, "user_text": "Добрый день! Какая цена?"},
            ) as resp:
                assert resp.status == 200
                turn_data = await resp.json()
                assert "reply" in turn_data
                assert not turn_data["finished"]

            # 5. /api/game/hint
            async with http.post(
                "http://127.0.0.1:18097/api/game/hint", json={"state": state}
            ) as resp:
                assert resp.status == 200
                hint_data = await resp.json()
                assert "hint" in hint_data
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
