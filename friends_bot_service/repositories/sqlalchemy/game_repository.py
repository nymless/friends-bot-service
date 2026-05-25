from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.domain import GameType, Player
from friends_bot_service.enums.enums import DateCol
from friends_bot_service.models.game_models import GameStats
from friends_bot_service.models.game_models import Player as PlayerORM
from friends_bot_service.repositories.mappers import player_to_domain


class SqlAlchemyGameRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_draw_today(
        self,
        bot_id: int,
        chat_id: int,
        game_type: GameType,
        today: date,
    ) -> bool:
        stmt = select(GameStats).where(
            GameStats.bot_id == bot_id,
            GameStats.chat_id == chat_id,
            (
                GameStats.last_win == today
                if game_type == GameType.WINNER
                else GameStats.last_lose == today
            ),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list_eligible_players(
        self,
        bot_id: int,
        chat_id: int,
        today: date,
    ) -> Sequence[Player]:
        skipped_players_stmt = select(GameStats.user_id).where(
            GameStats.bot_id == bot_id,
            GameStats.chat_id == chat_id,
            (getattr(GameStats, DateCol.LAST_WIN) == today)
            | (getattr(GameStats, DateCol.LAST_LOSE) == today),
        )

        stmt = select(PlayerORM).where(
            PlayerORM.bot_id == bot_id,
            PlayerORM.chat_id == chat_id,
            PlayerORM.is_active,
            PlayerORM.user_id.not_in(skipped_players_stmt),
        )
        result = await self._session.execute(stmt)
        return [player_to_domain(orm) for orm in result.scalars().all()]

    async def record_draw_result(
        self,
        bot_id: int,
        chat_id: int,
        winner_user_id: int,
        game_type: GameType,
        today: date,
    ) -> None:
        if game_type == GameType.WINNER:
            insert_vals = {"win_count": 1, "last_win": today}
            update_vals = {"win_count": GameStats.win_count + 1, "last_win": today}
        else:
            insert_vals = {"lose_count": 1, "last_lose": today}
            update_vals = {"lose_count": GameStats.lose_count + 1, "last_lose": today}

        stmt = (
            insert(GameStats)
            .values(
                bot_id=bot_id,
                chat_id=chat_id,
                user_id=winner_user_id,
                **insert_vals,
            )
            .on_conflict_do_update(
                index_elements=["bot_id", "chat_id", "user_id"],
                set_=update_vals,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()
