"""Векторные/текстовые хранилища базы знаний (RAG) — оба варианта локальные и бесплатные.

- SQLiteVectorStore (по умолчанию): чанки в основной БД, поиск — лексический
  BM25-lite в Python (services/ai/scoring.py). Ноль зависимостей и внешних вызовов.
- ChromaVectorStore (VECTOR_STORE=chroma): локальный ChromaDB в ./chroma_db.
  Семантический поиск встроенной локальной embedding-моделью Chroma (ONNX,
  скачивается один раз) — работает даже с LLM без embeddings API (Groq/OpenRouter).
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any, Protocol

from app.config import Settings


class VectorStore(Protocol):
    async def add(self, owner_id: int, chunks: list[str]) -> int: ...
    async def search(self, owner_id: int, query: str, top_k: int) -> list[str]: ...
    async def delete_for_owner(self, owner_id: int) -> int: ...
    async def count(self, owner_id: int) -> int: ...


class SQLiteVectorStore:
    """Встроенное хранилище: таблица knowledge_base + BM25-lite (без зависимостей)."""

    def __init__(self, session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def add(self, owner_id: int, chunks: list[str]) -> int:
        from app.db.repo.knowledge import KnowledgeRepo

        repo = KnowledgeRepo(self._session)
        for chunk in chunks:
            await repo.add_chunk(owner_id, chunk)
        return len(chunks)

    async def search(self, owner_id: int, query: str, top_k: int) -> list[str]:
        from app.db.repo.knowledge import KnowledgeRepo

        rows = await KnowledgeRepo(self._session).search(owner_id, query, top_k=top_k)
        return [row.content for row in rows]

    async def delete_for_owner(self, owner_id: int) -> int:
        from app.db.repo.knowledge import KnowledgeRepo

        return await KnowledgeRepo(self._session).delete_for_owner(owner_id)

    async def count(self, owner_id: int) -> int:
        from app.db.repo.knowledge import KnowledgeRepo

        return await KnowledgeRepo(self._session).count_for_owner(owner_id)


class ChromaVectorStore:
    """Локальный ChromaDB (VECTOR_STORE=chroma): данные в ./chroma_db, $0/мес."""

    def __init__(self, settings: Settings) -> None:
        import chromadb  # опциональная зависимость

        self._client = chromadb.PersistentClient(path=settings.chroma_dir)
        self._col = self._client.get_or_create_collection(
            "knowledge", metadata={"hnsw:space": "cosine"}
        )

    async def add(self, owner_id: int, chunks: list[str]) -> int:
        if not chunks:
            return 0
        # Стабильные ID: sha256 контента вместо builtin hash() (у него случайный
        # seed на процесс — дубли при перезагрузке докинули бы чанки заново).
        ids = [
            f"{owner_id}-{i}-{hashlib.sha256(c.encode()).hexdigest()[:16]}"
            for i, c in enumerate(chunks)
        ]

        def _add() -> None:
            self._col.add(documents=chunks, ids=ids, metadatas=[{"owner_id": owner_id}] * len(chunks))

        await asyncio.to_thread(_add)
        return len(chunks)

    async def search(self, owner_id: int, query: str, top_k: int) -> list[str]:
        def _query() -> dict[str, Any]:
            return self._col.query(
                query_texts=[query], n_results=top_k, where={"owner_id": owner_id}
            )

        result = await asyncio.to_thread(_query)
        docs = result.get("documents") or [[]]
        return list(docs[0]) if docs and docs[0] else []

    async def delete_for_owner(self, owner_id: int) -> int:
        def _delete() -> int:
            before = self._col.count()
            self._col.delete(where={"owner_id": owner_id})
            return before - self._col.count()

        return await asyncio.to_thread(_delete)

    async def count(self, owner_id: int) -> int:
        def _count() -> int:
            res = self._col.get(where={"owner_id": owner_id}, include=[])
            return len(res.get("ids", []))

        return await asyncio.to_thread(_count)


def build_vector_store(session, settings: Settings) -> VectorStore:
    """Фабрика: VECTOR_STORE=chroma (если chromadb установлен) → иначе встроенный SQLite."""
    if settings.vector_store.strip().lower() == "chroma":
        try:
            return ChromaVectorStore(settings)
        except ImportError:
            # chromadb не установлен — тихо откатываемся на встроенный SQLite (§8.3)
            return SQLiteVectorStore(session, settings)
    return SQLiteVectorStore(session, settings)