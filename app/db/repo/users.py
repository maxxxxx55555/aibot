import datetime as dt

from sqlalchemy import func, select, update

from app.db.models.base import utcnow
from app.db.models.user import User
from app.db.repo.base import BaseRepo


class UserRepo(BaseRepo[User]):
    model = User

    async def get_or_create(self, tg_id: int, tz: str = "UTC") -> User:
        user = await self.session.scalar(select(User).where(User.tg_id == tg_id))
        if user is None:
            user = User(tg_id=tg_id, tz=tz)
            self.session.add(user)
            await self.session.flush()
        return user

    async def get_by_tg_id(self, tg_id: int) -> User | None:
        return await self.session.scalar(select(User).where(User.tg_id == tg_id))

    async def reset_if_needed(self, user: User, period_days: int) -> bool:
        """Ленивый сброс скользящего периода (§4.3): без cron-задач."""
        now = utcnow()
        if user.period_reset_at <= now:
            await self.session.execute(
                update(User)
                .where(User.id == user.id, User.period_reset_at <= now)
                .values(messages_used=0, period_reset_at=now + dt.timedelta(days=period_days))
            )
            await self.session.refresh(user)
            return True
        return False

    async def set_plan(self, user: User, plan: str, period_days: int) -> None:
        """Активация/продление тарифа: план + обнулить usage + сдвинуть период."""
        from app.db.models.base import to_naive_utc

        now = utcnow()
        current_reset = to_naive_utc(user.period_reset_at) or now
        # Продление того же тарифа: период расширяется от max(now, текущий сброс)
        base = max(now, current_reset) if user.plan == plan else now
        user.plan = plan
        user.messages_used = 0
        user.period_reset_at = base + dt.timedelta(days=period_days)
        await self.session.flush()

    async def downgrade_to_free(self, user: User) -> None:
        user.plan = "free"
        await self.session.flush()

    async def count_all(self) -> int:
        return (await self.session.execute(select(func.count(User.id)))).scalar_one() or 0