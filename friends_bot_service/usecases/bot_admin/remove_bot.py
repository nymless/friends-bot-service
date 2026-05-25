from dataclasses import dataclass
from enum import StrEnum

from friends_bot_service.usecases.ports import BotRepository


class RemoveBotOutcome(StrEnum):
    NOT_FOUND = "not_found"
    SUCCESS = "success"


@dataclass(frozen=True, slots=True)
class RemoveBotCommand:
    bot_id: int
    owner_id: int


@dataclass(frozen=True, slots=True)
class RemoveBotResult:
    outcome: RemoveBotOutcome


class RemoveBot:
    async def execute(
        self,
        command: RemoveBotCommand,
        bots: BotRepository,
    ) -> RemoveBotResult:
        deactivated = await bots.deactivate_for_owner(
            command.bot_id,
            command.owner_id,
        )
        if not deactivated:
            return RemoveBotResult(outcome=RemoveBotOutcome.NOT_FOUND)
        return RemoveBotResult(outcome=RemoveBotOutcome.SUCCESS)
