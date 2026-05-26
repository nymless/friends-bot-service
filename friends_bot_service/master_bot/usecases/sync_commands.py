import logging
from collections.abc import Callable, Sequence

from aiogram import Bot
from aiogram.types import BotCommandScopeAllGroupChats

from friends_bot_service.bot_admin.domain import RegisteredBot
from friends_bot_service.bot_admin.interfaces import TokenCipherPort
from friends_bot_service.infra.texts.commands import BOT_COMMANDS

_logger = logging.getLogger(__name__)


class SyncBotCommands:
    def __init__(self, cipher: TokenCipherPort) -> None:
        self._cipher = cipher

    async def sync_runtime_bot(self, bot: Bot, bot_id: int) -> bool:
        try:
            await bot.set_my_commands(
                BOT_COMMANDS,
                scope=BotCommandScopeAllGroupChats(),
            )
            return True
        except Exception:
            _logger.exception("failed to sync commands bot_id=%s", bot_id)
            return False

    async def sync_registered_bot(self, registered_bot: RegisteredBot) -> bool:
        token = self._cipher.decrypt(registered_bot.encrypted_token)
        async with Bot(token=token) as temp_bot:
            return await self.sync_runtime_bot(temp_bot, registered_bot.bot_id)

    async def sync_all_registered_bots(
        self,
        registered_bots: Sequence[RegisteredBot],
        *,
        bot_name: Callable[[RegisteredBot], str],
    ) -> list[str]:
        failed_bot_names: list[str] = []

        for registered_bot in registered_bots:
            try:
                success = await self.sync_registered_bot(registered_bot)
            except Exception:
                _logger.exception(
                    "single command sync failed; Bot id=%s",
                    registered_bot.bot_id,
                )
                failed_bot_names.append(bot_name(registered_bot))
                continue

            if not success:
                failed_bot_names.append(bot_name(registered_bot))

        return failed_bot_names
