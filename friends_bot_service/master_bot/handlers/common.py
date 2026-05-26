import logging

from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from friends_bot_service.bot_admin.domain import RegisteredBot
from friends_bot_service.bot_admin.interfaces import TokenCipherPort
from friends_bot_service.infra.security import default_token_cipher

_logger = logging.getLogger(__name__)

_cipher: TokenCipherPort = default_token_cipher()

SET_DEFAULT_COMMANDS_ALL_CALLBACK = "set_default_commands:all"
SET_DEFAULT_COMMANDS_BOT_PREFIX = "set_default_commands:bot:"


async def try_delete_token_message(
    message: types.Message,
    update_id: str | None,
    flow: str,
) -> None:
    """Removes a token message from the chat history."""

    try:
        await message.delete()
    except Exception as exc:
        _logger.warning(
            "Update id=%s: token message delete failed; Flow=%s; Cause: %s",
            update_id,
            flow,
            exc,
        )


def get_bot_name(registered_bot: RegisteredBot) -> str:
    """Returns the bot display name as @username."""

    return f"@{registered_bot.username}"


def build_set_default_commands_keyboard(
    db_bots: list[RegisteredBot],
) -> types.InlineKeyboardMarkup:
    """Builds an inline keyboard for bot selection."""

    builder = InlineKeyboardBuilder()

    for registered_bot in db_bots:
        builder.button(
            text=get_bot_name(registered_bot),
            callback_data=(f"{SET_DEFAULT_COMMANDS_BOT_PREFIX}{registered_bot.bot_id}"),
        )

    builder.button(
        text="Обновить у всех",
        callback_data=SET_DEFAULT_COMMANDS_ALL_CALLBACK,
    )

    builder.adjust(2)
    return builder.as_markup()


async def edit_callback_message(
    callback: types.CallbackQuery,
    text: str,
) -> None:
    """Updates the text of the message with inline buttons."""

    message = callback.message
    if message is None:
        return

    edit_text = getattr(message, "edit_text", None)
    if callable(edit_text):
        await edit_text(text)
