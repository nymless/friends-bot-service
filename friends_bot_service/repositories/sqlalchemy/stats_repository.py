from collections.abc import Sequence

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.domain import GameType, StatLine
from friends_bot_service.models.game_models import GameStats
from friends_bot_service.models.game_models import Player as PlayerORM


class SqlAlchemyStatsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def top_for_chat(
        self,
        bot_id: int,
        chat_id: int,
        game_type: GameType,
    ) -> Sequence[StatLine]:
        sort_column = (
            GameStats.win_count
            if game_type == GameType.WINNER
            else GameStats.lose_count
        )

        stmt = (
            select(PlayerORM.full_name, sort_column)
            .join(
                GameStats,
                (GameStats.user_id == PlayerORM.user_id)
                & (GameStats.bot_id == PlayerORM.bot_id)
                & (GameStats.chat_id == PlayerORM.chat_id),
            )
            .where(
                GameStats.bot_id == bot_id,
                GameStats.chat_id == chat_id,
                sort_column > 0,
            )
            .order_by(desc(sort_column))
        )

        result = await self._session.execute(stmt)
        return [StatLine(full_name=name, count=count) for name, count in result.all()]
