from dataclasses import dataclass
from enum import StrEnum

from friends_bot_service.domain import RegisteredBot
from friends_bot_service.usecases.ports import BotRepository


class GetOwnerBotOutcome(StrEnum):
    NOT_FOUND = "not_found"
    SUCCESS = "success"


@dataclass(frozen=True, slots=True)
class GetOwnerBotCommand:
    owner_id: int
    bot_id: int


@dataclass(frozen=True, slots=True)
class GetOwnerBotResult:
    outcome: GetOwnerBotOutcome
    bot: RegisteredBot | None = None


class GetOwnerBot:
    async def execute(
        self,
        command: GetOwnerBotCommand,
        bots: BotRepository,
    ) -> GetOwnerBotResult:
        registered_bot = await bots.get_active_for_owner(
            command.owner_id,
            command.bot_id,
        )
        if registered_bot is None:
            return GetOwnerBotResult(outcome=GetOwnerBotOutcome.NOT_FOUND)
        return GetOwnerBotResult(
            outcome=GetOwnerBotOutcome.SUCCESS,
            bot=registered_bot,
        )
