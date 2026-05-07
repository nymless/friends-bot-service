from enum import StrEnum


class GameType(StrEnum):
    WINNER = "winner"
    LOSER = "loser"


class DateCol(StrEnum):
    LAST_WIN = "last_win"
    LAST_LOSE = "last_lose"


class CountCol(StrEnum):
    WIN_COUNT = "win_count"
    LOSE_COUNT = "lose_count"
