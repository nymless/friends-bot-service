from collections.abc import Callable

from aiogram import Dispatcher

from friends_bot_service.bot_admin.interfaces import BotRuntimePort
from friends_bot_service.infra.bot_manager.polling import PollingBotManager
from friends_bot_service.infra.bot_manager.webhook import WebhookBotManager


def create_polling_bot_manager(
    dispatcher_factory: Callable[[], Dispatcher],
) -> BotRuntimePort:
    """Creates a bot manager for polling mode."""

    return PollingBotManager(dispatcher_factory)


def create_webhook_bot_manager(
    base_url: str,
    secret_token: str,
) -> BotRuntimePort:
    """Creates a bot manager for webhook mode."""

    return WebhookBotManager(base_url, secret_token)
