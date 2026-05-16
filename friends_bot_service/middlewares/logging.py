import logging

from aiogram import BaseMiddleware
from aiogram.types.user import User

logger = logging.getLogger(__name__)

NON_COMMAND_LOG_PLACEHOLDER = "[non-command]"


def redact_message_text_for_log(text: str) -> str:
    """
    Prepare message text for logs.

    - Non-commands (text not starting with ``/``) are never logged verbatim.
    - ``/add_bot`` and ``/remove_bot`` log only the command name (no token).
    """

    if not text.startswith("/"):
        return NON_COMMAND_LOG_PLACEHOLDER

    if text.startswith("/remove_bot"):
        return "/remove_bot"
    if text.startswith("/add_bot"):
        return "/add_bot"
    return text


class LoggingMiddleware(BaseMiddleware):
    """
    Middleware for logging incoming events.

    - Injects update_id into the handler context for logging.
    - Logs all incoming events, including those ignored by handlers.
    - Does not log non-command message text (groups with privacy mode off, DMs).
    - Does not log arguments of ``/add_bot`` or ``/remove_bot`` (master bot tokens).
    """

    async def __call__(self, handler, event, data):
        update_id = getattr(event, "update_id", "N/A")
        data["update_id"] = update_id

        user: User | None = data.get("event_from_user")
        chat = data.get("event_chat")
        bot = data.get("bot")

        bot_id = bot.id if bot else "N/A"
        user_id = user.id if user else "N/A"
        full_name = user.full_name if user else "N/A"
        chat_id = chat.id if chat else "N/A"

        event_type = (
            event.event_type if hasattr(event, "event_type") else type(event).__name__
        )

        message_text = "N/A"
        if event.message and event.message.text is not None:
            message_text = redact_message_text_for_log(event.message.text)

        logger.info(
            f"Received [upd={update_id}] [bot={bot_id}] [chat={chat_id}] "
            f"[user={user_id}] [full={full_name}] [event={event_type}] "
            f"[message={message_text}]"
        )

        return await handler(event, data)
