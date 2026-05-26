from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from aiogram import Bot

from friends_bot_service.bot_admin import usecases as admin_usecases
from friends_bot_service.bot_admin.interfaces import (
    BotRepository,
    BotRuntimePort,
    TokenCipherPort,
)

from .sync_commands import SyncBotCommands


class AddBotOutcome(StrEnum):
    SUCCESS = "success"
    COMMANDS_SYNC_FAILED = "commands_sync_failed"


@dataclass(frozen=True, slots=True)
class AddBotData:
    bot_id: int
    username: str
    token: str
    owner_id: int


@dataclass(frozen=True, slots=True)
class AddBotResult:
    outcome: AddBotOutcome


class AddBot:
    def __init__(
        self,
        cipher: TokenCipherPort,
        commands_sync: SyncBotCommands | None = None,
    ) -> None:
        self._cipher = cipher
        self._register_bot = admin_usecases.RegisterBot()
        self._commands_sync = commands_sync or SyncBotCommands(cipher)

    async def persist(
        self,
        data: AddBotData,
        bots: BotRepository,
    ) -> admin_usecases.RegisterBotOutcome:
        result = await self._register_bot.execute(
            admin_usecases.RegisterBotData(
                bot_id=data.bot_id,
                username=data.username,
                encrypted_token=self._cipher.encrypt(data.token),
                owner_id=data.owner_id,
            ),
            bots,
        )
        return result.outcome

    async def activate(
        self,
        data: AddBotData,
        runtime: BotRuntimePort,
    ) -> AddBotResult:
        started_bot = cast(Bot, await runtime.start_bot(data.token))
        commands_synced = await self._commands_sync.sync_runtime_bot(
            started_bot,
            data.bot_id,
        )
        if commands_synced:
            return AddBotResult(outcome=AddBotOutcome.SUCCESS)
        return AddBotResult(outcome=AddBotOutcome.COMMANDS_SYNC_FAILED)
