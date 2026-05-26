from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.draw_entrant.domain import (
    DrawEntrant,
    DrawEntrantKey,
    RegisteredDrawEntrant,
)
from friends_bot_service.infra.models.draw_models import DrawEntrantORM
from friends_bot_service.infra.repositories.mappers import (
    draw_entrant_orm_to_registered_draw_entrant,
)


class SqlAlchemyDrawEntrantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: DrawEntrantKey) -> RegisteredDrawEntrant | None:
        stmt = select(DrawEntrantORM).where(
            DrawEntrantORM.bot_id == key.bot_id,
            DrawEntrantORM.chat_id == key.chat_id,
            DrawEntrantORM.user_id == key.user_id,
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return (
            draw_entrant_orm_to_registered_draw_entrant(orm)
            if orm is not None
            else None
        )

    async def list_active_for_chat(
        self, bot_id: int, chat_id: int
    ) -> Sequence[RegisteredDrawEntrant]:
        stmt = select(DrawEntrantORM).where(
            DrawEntrantORM.bot_id == bot_id,
            DrawEntrantORM.chat_id == chat_id,
            DrawEntrantORM.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        return [
            draw_entrant_orm_to_registered_draw_entrant(orm)
            for orm in result.scalars().all()
        ]

    async def upsert_active(self, draw_entrant: DrawEntrant) -> RegisteredDrawEntrant:
        result = await self._session.execute(
            insert(DrawEntrantORM)
            .values(
                bot_id=draw_entrant.bot_id,
                chat_id=draw_entrant.chat_id,
                user_id=draw_entrant.user_id,
                username=draw_entrant.username,
                full_name=draw_entrant.full_name,
            )
            .on_conflict_do_update(
                index_elements=["bot_id", "chat_id", "user_id"],
                set_={
                    "username": draw_entrant.username,
                    "full_name": draw_entrant.full_name,
                    "is_active": True,
                    "updated_at": func.now(),
                },
            )
            .returning(DrawEntrantORM)
        )
        await self._session.flush()
        return draw_entrant_orm_to_registered_draw_entrant(result.scalar_one())

    async def save(self, draw_entrant: RegisteredDrawEntrant) -> None:
        orm = await self._session.get(
            DrawEntrantORM,
            {
                "bot_id": draw_entrant.bot_id,
                "chat_id": draw_entrant.chat_id,
                "user_id": draw_entrant.user_id,
            },
        )
        if orm is None:
            msg = "draw entrant not found"
            raise LookupError(msg)
        orm.username = draw_entrant.username
        orm.full_name = draw_entrant.full_name
        orm.is_active = draw_entrant.is_active
        await self._session.flush()
