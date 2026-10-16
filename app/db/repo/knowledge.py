from sqlalchemy import delete, func, select

from app.db.models.knowledge import KnowledgeBase
from app.db.repo.base import BaseRepo
from app.services.ai.scoring import LexicalIndex


class KnowledgeRepo(BaseRepo[KnowledgeBase]):
    model = KnowledgeBase

    async def add_chunk(self, owner_id: int, content: str) -> KnowledgeBase:
        chunk = KnowledgeBase(
            owner_id=owner_id,
            content=content,
            tokens=max(len(content) // 4, 1),
        )
        self.session.add(chunk)
        await self.session.flush()
        return chunk

    async def for_owner(self, owner_id: int) -> list[KnowledgeBase]:
        result = await self.session.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.owner_id == owner_id)
            .order_by(KnowledgeBase.id)
        )
        return list(result.scalars().all())

    async def count_for_owner(self, owner_id: int) -> int:
        return (
            await self.session.execute(
                select(func.count(KnowledgeBase.id)).where(KnowledgeBase.owner_id == owner_id)
            )
        ).scalar_one() or 0

    async def search(self, owner_id: int, query: str, top_k: int = 5) -> list[KnowledgeBase]:
        """Топ-K релевантных чанков (BM25-lite, services/ai/scoring.py).

        Корпус — база знаний одного владельца; на объёмах базы знаний
        линейный проход по чанкам дешевле любого индекса.
        """
        rows = await self.for_owner(owner_id)
        if not rows:
            return []
        index = LexicalIndex([row.content for row in rows])
        return [rows[idx] for idx, _score in index.rank(query, top_k)]

    async def delete_for_owner(self, owner_id: int) -> int:
        result = await self.session.execute(
            delete(KnowledgeBase).where(KnowledgeBase.owner_id == owner_id)
        )
        return result.rowcount or 0