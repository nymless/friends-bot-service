from dataclasses import dataclass
from enum import StrEnum

from friends_bot_service.domain import GameType, StatLine
from friends_bot_service.texts.stats_text import STATS_MESSAGES
from friends_bot_service.usecases.ports import StatsRepository


class ShowStatsOutcome(StrEnum):
    USER_MISSING = "user_missing"
    EMPTY = "empty"
    SUCCESS = "success"


@dataclass(frozen=True, slots=True)
class ShowStatsCommand:
    bot_id: int
    chat_id: int
    user_id: int | None
    game_type: GameType


@dataclass(frozen=True, slots=True)
class ShowStatsResult:
    outcome: ShowStatsOutcome
    message: str | None = None
    lines: tuple[StatLine, ...] = ()


class ShowStats:
    async def execute(
        self,
        command: ShowStatsCommand,
        stats: StatsRepository,
    ) -> ShowStatsResult:
        if command.user_id is None:
            return ShowStatsResult(outcome=ShowStatsOutcome.USER_MISSING)

        rows = await stats.top_for_chat(
            command.bot_id,
            command.chat_id,
            command.game_type,
        )
        if not rows:
            return ShowStatsResult(
                outcome=ShowStatsOutcome.EMPTY,
                message="Статистика пока пуста. Сначала сыграйте в игру!",
            )

        title = STATS_MESSAGES[command.game_type]
        return ShowStatsResult(
            outcome=ShowStatsOutcome.SUCCESS,
            message=title,
            lines=tuple(rows),
        )
