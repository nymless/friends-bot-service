from dataclasses import dataclass
from enum import StrEnum

from aiogram import Bot
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError


class VerifyBotTokenOutcome(StrEnum):
    NETWORK_ERROR = "network_error"
    INVALID_TOKEN = "invalid_token"
    UNEXPECTED = "unexpected"
    USERNAME_MISSING = "username_missing"
    SUCCESS = "success"


@dataclass(frozen=True, slots=True)
class VerifiedBotInfo:
    bot_id: int
    username: str


async def verify_bot_token(
    token: str,
) -> tuple[VerifyBotTokenOutcome, VerifiedBotInfo | None]:
    try:
        async with Bot(token=token) as temp_bot:
            bot_info = await temp_bot.get_me()
    except TelegramNetworkError:
        return VerifyBotTokenOutcome.NETWORK_ERROR, None
    except TelegramUnauthorizedError:
        return VerifyBotTokenOutcome.INVALID_TOKEN, None
    except Exception:
        return VerifyBotTokenOutcome.UNEXPECTED, None

    if bot_info.username is None:
        return VerifyBotTokenOutcome.USERNAME_MISSING, None

    return VerifyBotTokenOutcome.SUCCESS, VerifiedBotInfo(
        bot_id=bot_info.id,
        username=bot_info.username,
    )
