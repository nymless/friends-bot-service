from aiogram import Bot

from friends_bot_service.infra.bootstrap.db import unit_of_work
from friends_bot_service.infra.bot_manager.base import BotManager
from friends_bot_service.infra.security import default_token_cipher


class WebhookBotManager(BotManager):
    """Bot manager implementation for webhook mode."""

    def __init__(self, base_url: str, secret_token: str):
        self._base_url = base_url
        self._secret_token = secret_token

    async def register_webhook(self, bot: Bot) -> Bot:
        """Registers webhook for an existing bot instance."""

        bot_user = await bot.get_me()
        webhook_url = f"{self._base_url}/webhook/{bot_user.id}"

        await bot.set_webhook(url=webhook_url, secret_token=self._secret_token)

        return bot

    async def unregister_webhook(self, bot: Bot) -> None:
        """Removes webhook registration for a bot instance."""

        await bot.delete_webhook()

    async def start_bot(self, token: str) -> Bot:
        """Registers webhook for a bot token."""

        bot = Bot(token=token)
        return await self.register_webhook(bot)

    async def stop_bot(self, bot_id: int, *, token: str | None = None) -> None:
        """Removes webhook registration for a bot token."""

        if token is None:
            msg = f"token is required to stop webhook bot {bot_id}"
            raise ValueError(msg)

        bot = Bot(token=token)
        try:
            await bot.delete_webhook()
        finally:
            await bot.session.close()

    async def stop_all(self) -> None:
        """Removes webhooks for all active bots from the database."""

        cipher = default_token_cipher()
        async with unit_of_work() as uow:
            active_bots = await uow.bots.list_all_active()

        for registered_bot in active_bots:
            token = cipher.decrypt(registered_bot.encrypted_token)
            await self.stop_bot(registered_bot.bot_id, token=token)
