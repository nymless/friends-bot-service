from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from friends_bot_service.infra.core.config import settings


def create_bot(token: str) -> Bot:
    """Build an aiogram Bot (game bots and master bot in load tests).

    When ``TELEGRAM_API_BASE_URL`` is unset, uses the default Telegram API.
    When set, routes Bot API calls to that base URL instead.
    """

    base_url = settings.TELEGRAM_API_BASE_URL
    if base_url is None:
        return Bot(token=token)

    api = TelegramAPIServer.from_base(base_url.rstrip("/"), is_local=True)
    session = AiohttpSession(api=api)
    return Bot(token=token, session=session)
