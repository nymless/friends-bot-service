from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.bot_admin.domain import RegisteredBot
from friends_bot_service.infra.models.bot_models import (
    RegisteredBot as RegisteredBotORM,
)
from friends_bot_service.infra.repositories.mappers import (
    registered_bot_orm_to_registered_bot,
)


class SqlAlchemyBotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        bot_id: int,
        username: str,
        encrypted_token: str,
        owner_id: int,
    ) -> RegisteredBot:
        stmt = (
            insert(RegisteredBotORM)
            .values(
                bot_id=bot_id,
                username=username,
                encrypted_token=encrypted_token,
                owner_id=owner_id,
                is_active=True,
            )
            .on_conflict_do_update(
                index_elements=["bot_id"],
                set_={
                    "username": username,
                    "encrypted_token": encrypted_token,
                    "is_active": True,
                    "updated_at": func.now(),
                },
            )
            .returning(RegisteredBotORM)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return registered_bot_orm_to_registered_bot(result.scalar_one())

    async def deactivate_for_owner(self, bot_id: int, owner_id: int) -> bool:
        stmt = (
            update(RegisteredBotORM)
            .where(
                RegisteredBotORM.bot_id == bot_id,
                RegisteredBotORM.owner_id == owner_id,
            )
            .values(is_active=False, updated_at=func.now())
            .returning(RegisteredBotORM.bot_id)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one_or_none() is not None

    async def touch_last_draw_attempt(self, bot_id: int) -> None:
        stmt = (
            update(RegisteredBotORM)
            .where(RegisteredBotORM.bot_id == bot_id)
            .values(last_draw_attempt_at=func.now(), updated_at=func.now())
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def deactivate_stale(self, cutoff: datetime) -> Sequence[tuple[int, str]]:
        stmt = (
            update(RegisteredBotORM)
            .where(
                RegisteredBotORM.is_active,
                func.coalesce(
                    RegisteredBotORM.last_draw_attempt_at,
                    RegisteredBotORM.created_at,
                )
                < cutoff,
            )
            .values(is_active=False, updated_at=func.now())
            .returning(RegisteredBotORM.bot_id, RegisteredBotORM.username)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return [(bot_id, username) for bot_id, username in result.all()]

    async def list_all_active(self) -> Sequence[RegisteredBot]:
        stmt = select(RegisteredBotORM).where(RegisteredBotORM.is_active)
        result = await self._session.execute(stmt)
        return [
            registered_bot_orm_to_registered_bot(orm) for orm in result.scalars().all()
        ]

    async def get_active_by_id(self, bot_id: int) -> RegisteredBot | None:
        stmt = select(RegisteredBotORM).where(
            RegisteredBotORM.bot_id == bot_id,
            RegisteredBotORM.is_active,
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return registered_bot_orm_to_registered_bot(orm) if orm is not None else None

    async def list_active_for_owner(self, owner_id: int) -> Sequence[RegisteredBot]:
        stmt = select(RegisteredBotORM).where(
            RegisteredBotORM.owner_id == owner_id,
            RegisteredBotORM.is_active,
        )
        result = await self._session.execute(stmt)
        return [
            registered_bot_orm_to_registered_bot(orm) for orm in result.scalars().all()
        ]

    async def get_active_for_owner(
        self,
        owner_id: int,
        bot_id: int,
    ) -> RegisteredBot | None:
        stmt = select(RegisteredBotORM).where(
            RegisteredBotORM.owner_id == owner_id,
            RegisteredBotORM.bot_id == bot_id,
            RegisteredBotORM.is_active,
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return registered_bot_orm_to_registered_bot(orm) if orm is not None else None
