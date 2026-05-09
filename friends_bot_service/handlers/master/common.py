import logging

from aiogram import Bot, Router, types
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommandScopeAllGroupChats
from aiogram.utils.keyboard import InlineKeyboardBuilder

from friends_bot_service.core.security import decrypt_token
from friends_bot_service.models.bot_models import RegisteredBot
from friends_bot_service.texts.commands import BOT_COMMANDS

logger = logging.getLogger(__name__)

router = Router()

SET_DEFAULT_COMMANDS_ALL_CALLBACK = "set_default_commands:all"
SET_DEFAULT_COMMANDS_BOT_PREFIX = "set_default_commands:bot:"


class MasterStates(StatesGroup):
    """States used by the master bot flows."""

    remove_token_state = State()


async def try_delete_token_message(
    message: types.Message, *, update_id: str, flow: str
) -> None:
    """Removes a token message from the chat history."""

    try:
        await message.delete()
    except Exception as exc:
        logger.warning(
            "Handler [upd=%s] [flow=%s] [details=token_message_delete_failed] %s",
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

    # One button per bot
    for registered_bot in db_bots:
        builder.button(
            text=get_bot_name(registered_bot),
            callback_data=(f"{SET_DEFAULT_COMMANDS_BOT_PREFIX}{registered_bot.bot_id}"),
        )

    # A separate button for bulk update
    builder.button(
        text="Обновить у всех",
        callback_data=SET_DEFAULT_COMMANDS_ALL_CALLBACK,
    )

    # Render buttons in two columns
    builder.adjust(2)
    return builder.as_markup()


async def sync_default_commands(bot: Bot, bot_id: int) -> bool:
    """
    Synchronizes the default commands for a bot.

    Sets scope of users for which the commands are revealed with "all group chats".
    """
    try:
        await bot.set_my_commands(BOT_COMMANDS, scope=BotCommandScopeAllGroupChats())
        return True
    except Exception:
        logger.exception("failed to sync commands bot_id=%s", bot_id)
        return False


async def sync_commands_for_bot(registered_bot: RegisteredBot) -> bool:
    """Updates the default commands for the selected bot."""

    # Decrypt the stored bot token
    token = decrypt_token(registered_bot.encrypted_token)

    # Sync commands using a temporary bot instance
    async with Bot(token=token) as temp_bot:
        return await sync_default_commands(temp_bot, registered_bot.bot_id)


async def edit_callback_message(
    callback: types.CallbackQuery,
    text: str,
) -> None:
    """Updates the text of the message with inline buttons."""

    message = callback.message
    if message is None:
        return

    # Make sure the message is editable in both real and test environments.
    # Real chats use `Message`, while tests often use mocks.
    # `InaccessibleMessage` has no edit.
    edit_text = getattr(message, "edit_text", None)
    if callable(edit_text):
        await edit_text(text)
