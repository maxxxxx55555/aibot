"""Smoke: приложение собирается целиком — роутеры, сервисы, фабрика провайдера."""

from __future__ import annotations


def test_app_assembles(settings):
    from app.bot.router import build_router
    from app.main import run  # noqa: F401 — импорт точки входа валиден
    from app.services.ai.provider import MockProvider, build_provider
    from app.services.ai.rag import RagService
    from app.services.billing.plans import PlanCatalog
    from app.services.billing.stars import StarsBillingService
    from app.services.limits.usage import UsageService

    catalog = PlanCatalog(settings)
    usage = UsageService(catalog, settings.period_days)
    billing = StarsBillingService(catalog, settings)
    rag = RagService(build_provider(settings), settings)

    router = build_router()
    assert len(router.sub_routers) == 7  # payments, admin, start, game, knowledge, menu, chat

    # Инварианты каталога (§4.1)
    assert catalog.get("free").price_stars == 0
    assert all(p.price_stars > 0 for p in catalog.paid())
    assert usage.catalog is catalog and billing.catalog is catalog
    assert isinstance(rag.provider, MockProvider)  # без ключа — mock (§6.1)


def test_settings_env_parsing():
    from app.config import Settings

    s = Settings(admin_ids="111, 222,333", llm_api_key="")
    assert s.admin_id_set == {111, 222, 333}
    assert s.use_mock_llm is True
    s2 = Settings(admin_ids="", llm_api_key="sk-x")
    assert s2.admin_id_set == set()
    assert s2.use_mock_llm is False


def test_get_settings_cached():
    from app.config import get_settings

    assert get_settings() is get_settings()


def test_llm_provider_presets():
    """$0-стек: пресеты Groq/OpenRouter резолвятся без явных base_url/model."""
    from app.config import Settings

    s = Settings(llm_provider="groq", llm_api_key="gsk_x")
    assert s.resolved_llm_base_url == "https://api.groq.com/openai/v1"
    assert s.resolved_llm_model == "llama-3.3-70b-versatile"

    s2 = Settings(llm_provider="openrouter", llm_api_key="sk-or-x")
    assert s2.resolved_llm_base_url == "https://openrouter.ai/api/v1"
    assert s2.resolved_llm_model.endswith(":free")

    # Явные значения имеют приоритет над пресетом
    s3 = Settings(llm_provider="groq", llm_api_key="k", llm_model="custom-model")
    assert s3.resolved_llm_model == "custom-model"
    assert s3.resolved_llm_base_url == "https://api.groq.com/openai/v1"

    # Неизвестный провайдер → безопасный дефолт
    s4 = Settings(llm_provider="unknown", llm_api_key="k")
    assert s4.resolved_llm_base_url == "https://api.groq.com/openai/v1"


async def test_vector_store_factory_sqlite_default(session, settings):
    from app.services.ai.vector_store import SQLiteVectorStore, build_vector_store

    store = build_vector_store(session, settings)
    assert isinstance(store, SQLiteVectorStore)
    user_id = 77
    assert await store.add(user_id, ["цена кофе 250"]) == 1
    assert await store.count(user_id) == 1
    results = await store.search(user_id, "сколько стоит кофе", top_k=3)
    assert results and "кофе" in results[0]
    await store.delete_for_owner(user_id)
    assert await store.count(user_id) == 0


async def test_vector_store_factory_chroma_fallback_without_pkg(session, settings):
    """chromadb не установлен → мягкий откат на SQLite (§8.3)."""
    from app.services.ai.vector_store import SQLiteVectorStore, build_vector_store

    settings = settings.model_copy(update={"vector_store": "chroma", "chroma_dir": "./chroma_test"})
    try:
        import chromadb  # noqa: F401

        chroma_installed = True
    except ImportError:
        chroma_installed = False

    store = build_vector_store(session, settings)
    if chroma_installed:
        assert not isinstance(store, SQLiteVectorStore)
    else:
        assert isinstance(store, SQLiteVectorStore)