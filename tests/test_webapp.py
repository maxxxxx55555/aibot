"""Health-сервер и REST API / WebApp симулятора продаж."""

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
    """Тестирование загрузки WebApp HTML и работы REST API симулятора продаж."""
    from aiohttp import ClientSession

    from app.main import start_webapp

    runner = await start_webapp("127.0.0.1", 18097, None, None, None)
    try:
        async with ClientSession() as http:
            # 1. GET /game_app
            async with http.get("http://127.0.0.1:18097/game_app") as resp:
                assert resp.status == 200
                html_text = await resp.text()
                assert "VIP Sales Simulator" in html_text

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
                start_data = await resp.json()
                state = start_data["state"]
                assert state["scenario_id"] == "b2b"
                assert "intro" in start_data

            # 4. POST /api/game/turn
            async with http.post(
                "http://127.0.0.1:18097/api/game/turn",
                json={
                    "state": state,
                    "user_text": "Мы предлагаем тест на 14 дней бесплатно!",
                },
            ) as resp:
                assert resp.status == 200
                turn_data = await resp.json()
                assert turn_data["state"]["turn"] == 2
                assert "reply" in turn_data
                assert not turn_data["finished"]

            # 5. POST /api/game/hint
            async with http.post(
                "http://127.0.0.1:18097/api/game/hint",
                json={"state": turn_data["state"]},
            ) as resp:
                assert resp.status == 200
                hint_data = await resp.json()
                assert "hint" in hint_data
                assert "Совет наставника" in hint_data["hint"]
    finally:
        await runner.cleanup()
