from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.draw.domain import DrawType
from friends_bot_service.draw_entrant.domain import DrawEntrant
from friends_bot_service.infra.models.draw_models import (
    ChatDrawClaimORM,
    DrawEntrantORM,
    DrawStatsORM,
)
from friends_bot_service.infra.repositories.mappers import (
    draw_entrant_orm_to_draw_entrant,
)


class SqlAlchemyDrawRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_draw_today(
        self,
        bot_id: int,
        chat_id: int,
        draw_type: DrawType,
        today: date,
    ) -> bool:
        date_column = (
            DrawStatsORM.last_win
            if draw_type == DrawType.WINNER
            else DrawStatsORM.last_lose
        )
        stmt = select(DrawStatsORM).where(
            DrawStatsORM.bot_id == bot_id,
            DrawStatsORM.chat_id == chat_id,
            date_column == today,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def has_claim_today(
        self,
        bot_id: int,
        chat_id: int,
        draw_type: DrawType,
        today: date,
    ) -> bool:
        stmt = select(ChatDrawClaimORM).where(
            ChatDrawClaimORM.bot_id == bot_id,
            ChatDrawClaimORM.chat_id == chat_id,
            ChatDrawClaimORM.draw_type == draw_type.value,
            ChatDrawClaimORM.draw_date == today,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list_eligible_draw_entrants(
        self,
        bot_id: int,
        chat_id: int,
        today: date,
    ) -> Sequence[DrawEntrant]:
        skipped_draw_entrants_stmt = select(DrawStatsORM.user_id).where(
            DrawStatsORM.bot_id == bot_id,
            DrawStatsORM.chat_id == chat_id,
            (DrawStatsORM.last_win == today) | (DrawStatsORM.last_lose == today),
        )

        stmt = select(DrawEntrantORM).where(
            DrawEntrantORM.bot_id == bot_id,
            DrawEntrantORM.chat_id == chat_id,
            DrawEntrantORM.is_active,
            DrawEntrantORM.user_id.not_in(skipped_draw_entrants_stmt),
        )
        result = await self._session.execute(stmt)
        return [draw_entrant_orm_to_draw_entrant(orm) for orm in result.scalars().all()]

    async def claim_draw(
        self,
        bot_id: int,
        chat_id: int,
        winner_user_id: int,
        draw_type: DrawType,
        today: date,
    ) -> None:
        claim_stmt = insert(ChatDrawClaimORM).values(
            bot_id=bot_id,
            chat_id=chat_id,
            draw_type=draw_type.value,
            draw_date=today,
            winner_user_id=winner_user_id,
        )
        await self._session.execute(claim_stmt)
        await self.record_draw_result(
            bot_id,
            chat_id,
            winner_user_id,
            draw_type,
            today,
        )

    async def record_draw_result(
        self,
        bot_id: int,
        chat_id: int,
        winner_user_id: int,
        draw_type: DrawType,
        today: date,
    ) -> None:
        if draw_type == DrawType.WINNER:
            insert_vals = {"win_count": 1, "last_win": today}
            update_vals = {
                "win_count": DrawStatsORM.win_count + 1,
                "last_win": today,
            }
        else:
            insert_vals = {"lose_count": 1, "last_lose": today}
            update_vals = {
                "lose_count": DrawStatsORM.lose_count + 1,
                "last_lose": today,
            }

        stmt = (
            insert(DrawStatsORM)
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
