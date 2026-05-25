from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.domain import Player, PlayerKey
from friends_bot_service.models.game_models import Player as PlayerORM
from friends_bot_service.repositories.mappers import player_to_domain


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: PlayerKey) -> Player | None:
        stmt = select(PlayerORM).where(
            PlayerORM.bot_id == key.bot_id,
            PlayerORM.chat_id == key.chat_id,
            PlayerORM.user_id == key.user_id,
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return player_to_domain(orm) if orm is not None else None

    async def list_active_for_chat(self, bot_id: int, chat_id: int) -> Sequence[Player]:
        stmt = select(PlayerORM).where(
            PlayerORM.bot_id == bot_id,
            PlayerORM.chat_id == chat_id,
            PlayerORM.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        return [player_to_domain(orm) for orm in result.scalars().all()]

    async def upsert_active(
        self,
        bot_id: int,
        chat_id: int,
        user_id: int,
        username: str | None,
        full_name: str,
    ) -> Player:
        result = await self._session.execute(
            insert(PlayerORM)
            .values(
                bot_id=bot_id,
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                full_name=full_name,
            )
            .on_conflict_do_update(
                index_elements=["bot_id", "chat_id", "user_id"],
                set_={
                    "username": username,
                    "full_name": full_name,
                    "is_active": True,
                    "updated_at": func.now(),
                },
            )
            .returning(PlayerORM)
        )
        await self._session.flush()
        return player_to_domain(result.scalar_one())

    async def save(self, player: Player) -> None:
        orm = await self._session.get(
            PlayerORM,
            {
                "bot_id": player.bot_id,
                "chat_id": player.chat_id,
                "user_id": player.user_id,
            },
        )
        if orm is None:
            msg = "player not found"
            raise LookupError(msg)
        orm.username = player.username
        orm.full_name = player.full_name
        orm.is_active = player.is_active
        await self._session.flush()
