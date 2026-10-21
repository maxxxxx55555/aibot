# 🤖 AI-Сотрудник — Telegram AI-ассистент для малого бизнеса

Telegram-бот «AI-Сотрудник»: отвечает клиентам вашего бизнеса 24/7, квалифицирует
лидов, записывает на консультации и отвечает по вашей базе знаний. Монетизация —
Telegram Stars (Freemium / Pro / Business).

**$0-стек:** SQLite + Groq/OpenRouter (бесплатные LLM) + ChromaDB (локальные векторы) —
ноль ежемесячных расходов на инфраструктуру.

> ⚡ **Быстрый старт:** [`QUICK_START.md`](QUICK_START.md) — бот работает за 5 минут, без Docker
> 💸 **Хостинг за $0:** [`FREE_DEPLOY.md`](FREE_DEPLOY.md) (Cloudflare Tunnel / Render Free)
> 🚀 **Деплой на VPS (€5):** [`DEPLOY.md`](DEPLOY.md) · 📊 **Мониторинг:** [`MONITORING.md`](MONITORING.md)
> ✅ **Чек-лист запуска:** [`CHECKLIST.md`](CHECKLIST.md) · 📣 **Маркетинг:** [`docs/LAUNCH_MATERIALS.md`](docs/LAUNCH_MATERIALS.md)
> 📚 Продукт и архитектура: [`docs/PRD.md`](docs/PRD.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/MARKETING.md`](docs/MARKETING.md)

## Возможности MVP (v1)

- ✅ Игровой тренажёр продаж (`/game`): 4-раундовый симулятор квалификации лидов с подсказками AI-наставника и WebApp
- ✅ Диалог с LLM от лица вашего бизнеса (OpenAI-совместимый API: Groq/OpenRouter/GLM/OpenAI)
- ✅ База знаний (RAG): текст сообщением или файл `.txt`/`.md` — бот отвечает строго по вашим данным
- ✅ Freemium-лимиты: атомарное списание, скользящие 30 дней, ленивый сброс
- ✅ Оплата Telegram Stars: invoice → pre_checkout → идемпотентная активация, проверка плательщика
- ✅ Admin: `/adminstats` (выручка/возвраты/тарифы), `/broadcast`, `/refund`
- ✅ Приватность: `/privacy`, `/forget_me` (CASCADE-удаление), retention-очистка истории
- ✅ UX: typing-индикатор, безопасный HTML, разбиение длинных ответов, `/cancel`
- ✅ Нативное меню команд (`setMyCommands`) синхронизируется при старте
- ✅ Миграции Alembic применяются автоматически при старте — dev и prod одинаковы
- ✅ Отказоустойчивость: ретраи LLM, fallback-провайдер, возврат лимита при сбое
- ✅ Mock-режим LLM: полный цикл разработки/тестов без внешних ключей

## Быстрый старт (2 минуты, без ключей)

```bash
git clone <repo> && cd bot
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt   # Windows; Linux/macOS: .venv/bin/pip ...
copy .env.example .env                          # вписать BOT_TOKEN от @BotFather
.venv\Scripts\pytest -q                         # 88 тестов: зелёные без LLM-ключа
.venv\Scripts\python -m app.main                # запуск бота (LLM в mock-режиме)
```

> Для установки пакетом: `pip install -e ".[dev]"` (и `".[chroma]"` — если нужен
> семантический поиск ChromaDB; по умолчанию RAG работает на встроенном лексическом поиске).

Без `LLM_API_KEY` бот работает на **MockProvider** — отвечает детерминированными
заглушками. Для реальных ответов впишите ключ:

```env
LLM_API_KEY=ваш_ключ
# GLM: https://open.bigmodel.cn/api/paas/v4
# OpenAI: https://api.openai.com/v1
```

## Тарифы

| Тариф | Цена | Лимит/30 дней | Функции |
|---|---|---|---|
| Free | 0 ⭐️ | 30 | базовый чат |
| Pro | 100 ⭐️ | 500 | + база знаний (RAG) |
| Business | 250 ⭐️ | 2000 | + RAG, приоритет |

Цены/лимиты переопределяются через `.env` (`PRO_PRICE_STARS`, `PRO_LIMIT`, …) — без релиза кода.

## Архитектура

Модульный монолит со строгой слоистостью:

```
bot/handlers (Telegram I/O) → services (бизнес-логика) → db/repo (доступ к данным)
```

- **Стек:** Python 3.11+, aiogram 3, SQLAlchemy 2 (async), SQLite (dev) / PostgreSQL 16 + pgvector (prod), Redis (опц.)
- **LLM:** единый интерфейс провайдера с пресетами Groq/OpenRouter/OpenAI/GLM → смена модели без правок кода
- **RAG:** лексический BM25-lite встроен (без зависимостей); `VECTOR_STORE=chroma` — локальная семантическая модель
- **Платежи:** идемпотентность по `telegram_payment_charge_id` (UNIQUE) + проверка, что платит владелец инвойса
- **Лимиты:** атомарный `UPDATE … WHERE messages_used < limit` — гонки исключены

Подробно (схема БД, поток Stars, edge cases, безопасность, масштабирование):
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Docker

```bash
# Dev-профиль: только бот + SQLite
docker compose up -d --build

# Prod-профиль: + PostgreSQL (pgvector) + Redis
# DATABASE_URL=postgresql+asyncpg://bot:secret@postgres:5432/aiemployee
# REDIS_URL=redis://redis:6379/0
docker compose --profile prod up -d --build
```

## Тесты

```bash
pytest -q                                    # 96 тестов: лимиты, тренажёр продаж, биллинг, RAG, роутеры, WebApp
ruff check app migrations tests              # линтер
python -m compileall -q app migrations tests  # синтаксическая проверка
```

Тесты используют SQLite in-memory и MockProvider — без сети и секретов.

## Roadmap

- [x] v1.1: alembic-миграции (автозапуск при старте), webhook-режим, healthcheck, retention, `/privacy`
- [ ] v1.2: summary длинных диалогов, экспорт лидов, аналитика воронки
- [ ] v2: pgvector HNSW, CRM-интеграции, реферальная программа
- [ ] v3: white label, API для Enterprise, автоматизации (вебхуки → CRM)

## Структура

```
app/
├── main.py                  # сборка и запуск (polling/webhook, graceful shutdown)
├── config.py                # pydantic-settings — единственный источник конфигурации
├── db/                      # движок, автозапуск Alembic, модели, repo
├── services/
│   ├── ai/                  # provider (OpenAI-compat | mock), prompt, context, rag, scoring
│   ├── billing/             # каталог тарифов, Telegram Stars
│   ├── limits/              # атомарное списание, скользящий период
│   └── maintenance.py       # retention-очистка истории
├── bot/                     # роутер, middlewares, handlers, keyboards, texts, helpers
└── utils/                   # логирование без секретов, безопасный HTML/markdown-lite
```
