from dataclasses import dataclass
from enum import StrEnum

from friends_bot_service.bot_admin.interfaces import BotRepository


class RegisterBotOutcome(StrEnum):
    SUCCESS = "success"


@dataclass(frozen=True, slots=True)
class RegisterBotData:
    bot_id: int
    username: str
    encrypted_token: str
    owner_id: int


@dataclass(frozen=True, slots=True)
class RegisterBotResult:
    outcome: RegisterBotOutcome


class RegisterBot:
    async def execute(
        self,
        data: RegisterBotData,
        bots: BotRepository,
    ) -> RegisterBotResult:
        await bots.upsert(
            bot_id=data.bot_id,
            username=data.username,
            encrypted_token=data.encrypted_token,
            owner_id=data.owner_id,
        )
        return RegisterBotResult(outcome=RegisterBotOutcome.SUCCESS)
