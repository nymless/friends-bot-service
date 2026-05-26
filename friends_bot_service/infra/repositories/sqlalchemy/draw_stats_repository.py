from collections.abc import Sequence

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.draw.domain import GameType
from friends_bot_service.draw_stats.domain import StatLine
from friends_bot_service.infra.models.draw_models import DrawEntrantORM, DrawStatsORM


class SqlAlchemyDrawStatsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def top_for_chat(
        self,
        bot_id: int,
        chat_id: int,
        game_type: GameType,
    ) -> Sequence[StatLine]:
        sort_column = (
            DrawStatsORM.win_count
            if game_type == GameType.WINNER
            else DrawStatsORM.lose_count
        )

        stmt = (
            select(DrawEntrantORM.full_name, sort_column)
            .join(
                DrawStatsORM,
                (DrawStatsORM.user_id == DrawEntrantORM.user_id)
                & (DrawStatsORM.bot_id == DrawEntrantORM.bot_id)
                & (DrawStatsORM.chat_id == DrawEntrantORM.chat_id),
            )
            .where(
                DrawStatsORM.bot_id == bot_id,
                DrawStatsORM.chat_id == chat_id,
                sort_column > 0,
            )
            .order_by(desc(sort_column))
        )

        result = await self._session.execute(stmt)
        return [StatLine(full_name=name, count=count) for name, count in result.all()]
