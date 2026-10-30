"""Конфигурация приложения — единственный источник настроек (12-factor).

Никаких прямых os.getenv в других модулях: только app.config.Settings.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

# Пресеты бесплатных LLM-провайдеров ($0/мес): provider → (base_url, model).
# Явные LLM_BASE_URL / LLM_MODEL в .env всегда имеют приоритет над пресетом.
LLM_PRESETS: dict[str, tuple[str, str]] = {
    "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "openrouter": ("https://openrouter.ai/api/v1", "meta-llama/llama-3.1-8b-instruct:free"),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "glm": ("https://open.bigmodel.cn/api/paas/v4", "glm-4.5"),
}
_DEFAULT_PRESET = LLM_PRESETS["groq"]

# Абсолютный путь: SQLite-файл не зависит от текущего каталога запуска (Docker/workers).
DEFAULT_DATABASE_URL = f"sqlite+aiosqlite:///{(BASE_DIR / 'data' / 'bot.db').as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Telegram ---
    bot_token: str = ""

    # --- Database / cache ---
    database_url: str = DEFAULT_DATABASE_URL
    redis_url: str | None = None

    # --- LLM ($0-стек: бесплатные провайдеры через OpenAI-совместимый API) ---
    # llm_provider выбирает пресет base_url+model; явные LLM_BASE_URL/LLM_MODEL имеют приоритет.
    # Провайдеры: groq (бесплатный tier) | openrouter (модели :free) | openai | glm | custom
    llm_provider: str = "groq"
    llm_api_key: str = ""
    llm_base_url: str = ""  # пусто → из пресета llm_provider
    llm_model: str = ""     # пусто → из пресета llm_provider
    llm_fallback_base_url: str = ""
    llm_fallback_api_key: str = ""
    llm_fallback_model: str = ""
    llm_max_retries: int = 3
    llm_timeout: float = 60.0
    llm_mock: bool = False

    # --- Vector store (RAG) ---
    # sqlite (по умолчанию, встроенный cosine-поиск по BLOB) | chroma (локальный ./chroma_db)
    vector_store: str = "sqlite"
    chroma_dir: str = "./chroma_db"

    # --- Embeddings / RAG ---
    embedding_model: str = "embedding-3"
    embedding_dim: int = 1024
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 150
    rag_top_k: int = 5

    # --- Context ---
    context_window: int = 20
    context_token_budget: int = 3000
    summary_trigger_messages: int = 40

    # --- Plans / limits ---
    period_days: int = 30
    free_limit: int = 30
    pro_limit: int = 500
    business_limit: int = 2000
    pro_price_stars: int = 100
    business_price_stars: int = 250

    # --- Rate limiting / safety ---
    rate_limit_per_minute: int = 20
    max_message_len: int = 4000
    admin_ids: str = ""
    default_tz: str = "UTC"
    support_username: str = ""  # @username поддержки (показывается в /help и ошибках)
    retention_days: int = 90  # хранение истории сообщений (0 = отключено)

    # --- Webhook (prod) / health ---
    webhook_mode: bool = False  # False = long polling (dev), True = webhook (prod)
    webhook_base_url: str = ""  # https://bot.example.com
    webhook_secret_path: str = "tg-webhook"  # путь: {webhook_base_url}/{webhook_secret_path}
    webhook_secret_token: str = ""  # X-Telegram-Bot-Api-Secret-Token; пусто → сгенерировать
    webapp_host: str = "0.0.0.0"
    # WEBAPP_PORT задаёт порт явно; PORT читается для PaaS (Render/Railway)
    webapp_port: int = Field(
        default=8080, validation_alias=AliasChoices("WEBAPP_PORT", "PORT")
    )

    # --- Misc ---
    log_level: str = "INFO"

    @property
    def webapp_url(self) -> str:
        """Динамический URL WebApp приложения."""
        if self.webhook_base_url:
            return f"{self.webhook_base_url.rstrip('/')}/game_app"
        return ""

    @property
    def admin_id_set(self) -> set[int]:
        """ADMIN_IDS терпим к формату: «1,2 3;4», пробелы, мусор — пропускаем с варнингом."""
        if not self.admin_ids.strip():
            return set()
        import logging

        ids: set[int] = set()
        for token in self.admin_ids.replace(";", ",").replace(" ", ",").split(","):
            token = token.strip()
            if not token:
                continue
            try:
                ids.add(int(token))
            except ValueError:
                logging.getLogger(__name__).warning("ADMIN_IDS: пропущен мусор %r", token)
        return ids

    @property
    def use_mock_llm(self) -> bool:
        """Mock-режим: без ключа или принудительно через LLM_MOCK=1."""
        return self.llm_mock or not self.llm_api_key.strip()

    # Пресеты LLM-провайдеров — модульная константа LLM_PRESETS (см. начало файла).
    @property
    def resolved_llm_base_url(self) -> str:
        if self.llm_base_url.strip():
            return self.llm_base_url
        preset = LLM_PRESETS.get(self.llm_provider.strip().lower())
        return preset[0] if preset else _DEFAULT_PRESET[0]

    @property
    def resolved_llm_model(self) -> str:
        if self.llm_model.strip():
            return self.llm_model
        preset = LLM_PRESETS.get(self.llm_provider.strip().lower())
        return preset[1] if preset else _DEFAULT_PRESET[1]


@lru_cache
def get_settings() -> Settings:
    return Settings()