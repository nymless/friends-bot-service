from dataclasses import dataclass
from enum import StrEnum

from friends_bot_service.draw import domain
from friends_bot_service.draw_stats.domain import StatLine
from friends_bot_service.draw_stats.interfaces import StatsRepository
from friends_bot_service.infra.texts import stats_text as text


class ShowStatsOutcome(StrEnum):
    USER_MISSING = "user_missing"
    EMPTY = "empty"
    SUCCESS = "success"


@dataclass(frozen=True, slots=True)
class ShowStatsData:
    bot_id: int
    chat_id: int
    user_id: int | None
    draw_type: domain.DrawType


@dataclass(frozen=True, slots=True)
class ShowStatsResult:
    outcome: ShowStatsOutcome
    message: str | None = None
    lines: tuple[StatLine, ...] = ()


class ShowStats:
    async def execute(
        self,
        data: ShowStatsData,
        stats: StatsRepository,
    ) -> ShowStatsResult:
        if data.user_id is None:
            return ShowStatsResult(outcome=ShowStatsOutcome.USER_MISSING)

        rows = await stats.top_for_chat(
            data.bot_id,
            data.chat_id,
            data.draw_type,
        )
        if not rows:
            return ShowStatsResult(
                outcome=ShowStatsOutcome.EMPTY,
                message=text.STATS_EMPTY_MESSAGE,
            )

        title = text.STATS_MESSAGES[data.draw_type]
        return ShowStatsResult(
            outcome=ShowStatsOutcome.SUCCESS,
            message=title,
            lines=tuple(rows),
        )
