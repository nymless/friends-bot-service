from dataclasses import dataclass
from enum import StrEnum

from friends_bot_service.domain import PlayerKey
from friends_bot_service.usecases.ports import UserRepository


class UnregisterPlayerOutcome(StrEnum):
    USER_MISSING = "user_missing"
    NOT_FOUND = "not_found"
    ALREADY_INACTIVE = "already_inactive"
    SUCCESS = "success"


@dataclass(frozen=True, slots=True)
class UnregisterPlayerCommand:
    bot_id: int
    chat_id: int
    user_id: int | None


@dataclass(frozen=True, slots=True)
class UnregisterPlayerResult:
    outcome: UnregisterPlayerOutcome


class UnregisterPlayer:
    async def execute(
        self,
        command: UnregisterPlayerCommand,
        users: UserRepository,
    ) -> UnregisterPlayerResult:
        if command.user_id is None:
            return UnregisterPlayerResult(outcome=UnregisterPlayerOutcome.USER_MISSING)

        key = PlayerKey(
            bot_id=command.bot_id,
            chat_id=command.chat_id,
            user_id=command.user_id,
        )
        player = await users.get(key)

        if player is None:
            return UnregisterPlayerResult(outcome=UnregisterPlayerOutcome.NOT_FOUND)

        if not player.is_active:
            return UnregisterPlayerResult(
                outcome=UnregisterPlayerOutcome.ALREADY_INACTIVE
            )

        player.is_active = False
        await users.save(player)
        return UnregisterPlayerResult(outcome=UnregisterPlayerOutcome.SUCCESS)
