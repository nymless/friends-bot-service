from aiogram import Bot

from friends_bot_service.bot_manager.base import BotManager


class WebhookBotManager(BotManager):
    """Bot manager implementation for webhook mode."""

    def __init__(self, base_url: str, secret_token: str):
        super().__init__()
        self._base_url = base_url
        self._secret_token = secret_token

    async def start_bot(self, token: str) -> Bot:
        """Starts a bot with webhook."""

        bot = Bot(token=token)
        bot_user = await bot.get_me()

        existing_bot = self.get_bot(bot_user.id)
        if existing_bot is not None:
            await bot.session.close()
            return existing_bot

        webhook_url = f"{self._base_url}/webhook/{bot_user.id}"

        await bot.set_webhook(url=webhook_url, secret_token=self._secret_token)

        self._active_bots[bot_user.id] = bot
        return bot

    async def stop_bot(self, bot_id: int):
        """Stops a bot with webhook."""

        bot = self._active_bots.pop(bot_id, None)

        if bot:
            await bot.delete_webhook()
            await bot.session.close()
