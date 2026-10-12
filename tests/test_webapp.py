"""Health-сервер и REST API игры: /health и /api/game/*."""

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


async def test_game_rest_api():
    """Проверка REST API эндпоинтов игры для веб/мобильных приложений."""
    from aiohttp import ClientSession

    from app.main import start_webapp

    runner = await start_webapp("127.0.0.1", 18097, None, None, None)
    base_url = "http://127.0.0.1:18097"
    try:
        async with ClientSession() as http:
            # 1. Scenarios
            async with http.get(f"{base_url}/api/game/scenarios") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "b2b" in data["scenarios"]

            # 2. Start
            async with http.post(
                f"{base_url}/api/game/start", json={"scenario_id": "b2b"}
            ) as resp:
                assert resp.status == 200
                start_data = await resp.json()
                state = start_data["state"]
                assert state["turn"] == 1

            # 3. Hint
            async with http.post(
                f"{base_url}/api/game/hint", json={"state": state}
            ) as resp:
                assert resp.status == 200
                hint_data = await resp.json()
                assert "Совет наставника" in hint_data["hint"]

            # 4. Turn
            async with http.post(
                f"{base_url}/api/game/turn",
                json={"state": state, "user_text": "Добрый день! Хотим заказать демо."},
            ) as resp:
                assert resp.status == 200
                turn_data = await resp.json()
                assert turn_data["state"]["turn"] == 2
                assert not turn_data["finished"]

            # 5. Game App Page
            async with http.get(f"{base_url}/game_app") as resp:
                assert resp.status == 200
                text = await resp.text()
                assert "VIP Sales Simulator" in text
    finally:
        await runner.cleanup()
