from enum import StrEnum


class BotMode(StrEnum):
    """Bot mode enum."""

    POLLING = "polling"
    WEBHOOK = "webhook"


class DateCol(StrEnum):
    """Win/Lose date column enum."""

    LAST_WIN = "last_win"
    LAST_LOSE = "last_lose"


class CountCol(StrEnum):
    """Win/Lose count column enum."""

    WIN_COUNT = "win_count"
    LOSE_COUNT = "lose_count"
