from dataclasses import dataclass
from enum import StrEnum

from friends_bot_service.usecases.ports import BotRepository


class RegisterBotOutcome(StrEnum):
    REGISTRATION_DISABLED = "registration_disabled"
    SUCCESS = "success"


@dataclass(frozen=True, slots=True)
class RegisterBotCommand:
    bot_id: int
    username: str
    encrypted_token: str
    owner_id: int


@dataclass(frozen=True, slots=True)
class RegisterBotResult:
    outcome: RegisterBotOutcome


class RegisterBot:
    def __init__(self, registration_enabled: bool) -> None:
        self._registration_enabled = registration_enabled

    async def execute(
        self,
        command: RegisterBotCommand,
        bots: BotRepository,
    ) -> RegisterBotResult:
        if not self._registration_enabled:
            return RegisterBotResult(outcome=RegisterBotOutcome.REGISTRATION_DISABLED)

        await bots.upsert(
            bot_id=command.bot_id,
            username=command.username,
            encrypted_token=command.encrypted_token,
            owner_id=command.owner_id,
        )
        return RegisterBotResult(outcome=RegisterBotOutcome.SUCCESS)
