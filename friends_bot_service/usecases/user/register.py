from dataclasses import dataclass
from enum import StrEnum

from friends_bot_service.usecases.ports import UserRepository


class RegisterPlayerOutcome(StrEnum):
    USER_MISSING = "user_missing"
    REGISTRATION_DISABLED = "registration_disabled"
    SUCCESS = "success"


@dataclass(frozen=True, slots=True)
class RegisterPlayerCommand:
    bot_id: int
    chat_id: int
    user_id: int | None
    username: str | None
    full_name: str


@dataclass(frozen=True, slots=True)
class RegisterPlayerResult:
    outcome: RegisterPlayerOutcome


class RegisterPlayer:
    def __init__(self, registration_enabled: bool) -> None:
        self._registration_enabled = registration_enabled

    async def execute(
        self,
        command: RegisterPlayerCommand,
        users: UserRepository,
    ) -> RegisterPlayerResult:
        if command.user_id is None:
            return RegisterPlayerResult(outcome=RegisterPlayerOutcome.USER_MISSING)

        if not self._registration_enabled:
            return RegisterPlayerResult(
                outcome=RegisterPlayerOutcome.REGISTRATION_DISABLED
            )

        await users.upsert_active(
            command.bot_id,
            command.chat_id,
            command.user_id,
            command.username,
            command.full_name,
        )
        return RegisterPlayerResult(outcome=RegisterPlayerOutcome.SUCCESS)
