from dataclasses import dataclass
from enum import StrEnum

from friends_bot_service.domain import Player
from friends_bot_service.usecases.ports import UserRepository


class ListPlayersOutcome(StrEnum):
    USER_MISSING = "user_missing"
    EMPTY = "empty"
    SUCCESS = "success"


@dataclass(frozen=True, slots=True)
class ListPlayersCommand:
    bot_id: int
    chat_id: int
    user_id: int | None


@dataclass(frozen=True, slots=True)
class ListPlayersResult:
    outcome: ListPlayersOutcome
    players: tuple[Player, ...] = ()


class ListPlayers:
    async def execute(
        self,
        command: ListPlayersCommand,
        users: UserRepository,
    ) -> ListPlayersResult:
        if command.user_id is None:
            return ListPlayersResult(outcome=ListPlayersOutcome.USER_MISSING)

        players = await users.list_active_for_chat(command.bot_id, command.chat_id)
        if not players:
            return ListPlayersResult(outcome=ListPlayersOutcome.EMPTY)

        return ListPlayersResult(
            outcome=ListPlayersOutcome.SUCCESS,
            players=tuple(players),
        )
