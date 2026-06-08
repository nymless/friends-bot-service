import logging
from dataclasses import dataclass

from aiogram import Bot

from friends_bot_service.bot_admin.interfaces import (
    BotRepository,
    BotRuntimePort,
    TokenCipherPort,
)

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LoadActiveBotsResult:
    started_count: int


class LoadActiveBots:
    def __init__(self, token_cipher: TokenCipherPort) -> None:
        self._token_cipher = token_cipher

    async def execute(
        self,
        bots: BotRepository,
        runtime: BotRuntimePort,
    ) -> LoadActiveBotsResult:
        bots_to_load = await bots.list_all_active()
        started_count = 0

        for registered_bot in bots_to_load:
            token = self._token_cipher.decrypt(registered_bot.encrypted_token)
            started_bot = await runtime.start_bot(token)
            if isinstance(started_bot, Bot):
                await started_bot.session.close()
            started_count += 1
            _logger.info(
                "Bot started; Bot id=%s; Username=%s",
                registered_bot.bot_id,
                registered_bot.username,
            )

        return LoadActiveBotsResult(started_count=started_count)
