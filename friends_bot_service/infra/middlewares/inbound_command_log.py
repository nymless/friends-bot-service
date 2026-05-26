import logging

from aiogram import BaseMiddleware, Dispatcher

from friends_bot_service.infra.core.config import settings

logger = logging.getLogger(__name__)


def redact_command_text_for_log(text: str) -> str:
    """
    Prepare command text for access logs.

    `/add_bot` and `/remove_bot` log only the command name (no token).
    """

    if text.startswith("/remove_bot"):
        return "/remove_bot"
    if text.startswith("/add_bot"):
        return "/add_bot"
    return text


class InboundCommandLogMiddleware(BaseMiddleware):
    """
    Optional access log for inbound slash-commands.

    Logs only message text that starts with `/`. Does not log display names.
    """

    async def __call__(self, handler, event, data):
        message = getattr(event, "message", None)
        text = message.text if message is not None else None

        if text is not None and text.startswith("/"):
            bot = data.get("bot")
            user = data.get("event_from_user")
            chat = data.get("event_chat")

            logger.info(
                "Inbound [upd=%s] [bot=%s] [chat=%s] [user=%s] [event=%s] [message=%s]",
                getattr(event, "update_id", None),
                bot.id if bot else None,
                chat.id if chat else None,
                user.id if user else None,
                event.event_type
                if hasattr(event, "event_type")
                else type(event).__name__,
                redact_command_text_for_log(text),
            )

        return await handler(event, data)


def register_inbound_command_log_middleware(dp: Dispatcher) -> None:
    """Registers inbound access-log middleware when enabled in settings."""

    if settings.LOG_INBOUND_COMMANDS:
        dp.update.middleware(InboundCommandLogMiddleware())
