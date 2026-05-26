from dataclasses import dataclass
from enum import StrEnum

from friends_bot_service.bot_admin.interfaces import BotRepository


class RemoveBotOutcome(StrEnum):
    NOT_FOUND = "not_found"
    SUCCESS = "success"


@dataclass(frozen=True, slots=True)
class RemoveBotData:
    bot_id: int
    owner_id: int


@dataclass(frozen=True, slots=True)
class RemoveBotResult:
    outcome: RemoveBotOutcome


class RemoveBot:
    async def execute(
        self,
        data: RemoveBotData,
        bots: BotRepository,
    ) -> RemoveBotResult:
        deactivated = await bots.deactivate_for_owner(
            data.bot_id,
            data.owner_id,
        )
        if not deactivated:
            return RemoveBotResult(outcome=RemoveBotOutcome.NOT_FOUND)
        return RemoveBotResult(outcome=RemoveBotOutcome.SUCCESS)
