from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.exceptions import TelegramUnauthorizedError

from friends_bot_service.handlers.master.add_bot import handle_add_bot
from friends_bot_service.handlers.master.common import (
    build_set_default_commands_keyboard,
    edit_callback_message,
    get_bot_name,
)
from friends_bot_service.handlers.master.remove_bot import handle_remove_bot
from friends_bot_service.handlers.master.set_default_commands import (
    set_default_commands,
    set_default_commands_for_all_bots,
    set_default_commands_for_selected_bot,
)
from friends_bot_service.texts.master_text import (
    BOT_REGISTRATION_DISABLED,
    CALLBACK_BOT_NOT_OWNED,
    CALLBACK_INVALID_BOT,
    CHOOSE_BOT_FOR_COMMAND_SYNC,
    NO_BOTS_FOR_COMMAND_SYNC,
    REMOVE_BOT_NOT_FOUND,
    bot_registered_success,
    bot_registered_with_commands_warning,
    bot_removed_success,
    commands_bulk_failure,
    commands_updated_for_bot,
    token_command_usage,
)
from friends_bot_service.texts.system import INVALID_BOT_TOKEN
from tests.helpers.uow import invoke_run_with_unit_of_work

_last_uow: dict[str, AsyncMock] = {}


async def capture_uow_callback(callback, *, message=None):
    uow = AsyncMock()
    uow.bots = AsyncMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    _last_uow["uow"] = uow
    return await callback(uow)


async def capture_remove_bot_callback(
    callback, *, message=None, deactivated: bool = False
):
    uow = AsyncMock()
    uow.bots = AsyncMock()
    uow.bots.deactivate_for_owner = AsyncMock(return_value=deactivated)
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    _last_uow["uow"] = uow
    return await callback(uow)


async def capture_remove_bot_not_deactivated(callback, *, message=None):
    return await capture_remove_bot_callback(
        callback, message=message, deactivated=False
    )


async def capture_remove_bot_deactivated(callback, *, message=None):
    return await capture_remove_bot_callback(
        callback, message=message, deactivated=True
    )


def build_command_args(args: str | None) -> SimpleNamespace:
    """Minimal CommandObject stand-in for handler tests."""

    return SimpleNamespace(args=args)


def build_message(*, user_id: int | None = 20) -> AsyncMock:
    """Builds a minimal aiogram message mock for master handler tests."""

    message = AsyncMock()
    message.from_user = None if user_id is None else SimpleNamespace(id=user_id)
    return message


class FakeTempBot:
    """Minimal async context manager used to fake Bot(token) in master tests."""

    def __init__(self, *, bot_info=None, get_me_exception: Exception | None = None):
        self._bot_info = bot_info
        self._get_me_exception = get_me_exception

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get_me(self):
        if self._get_me_exception is not None:
            raise self._get_me_exception
        return self._bot_info


def build_registered_bot(bot_id: int, username: str):
    """Builds a lightweight registered bot object for tests."""

    return SimpleNamespace(bot_id=bot_id, username=username)


def build_callback(
    *,
    user_id: int | None = 20,
    data: str | None = "callback-data",
    with_message: bool = True,
) -> AsyncMock:
    """Builds a minimal aiogram callback query mock for master tests."""

    callback = AsyncMock()
    callback.from_user = None if user_id is None else SimpleNamespace(id=user_id)
    callback.data = data
    callback.message = AsyncMock() if with_message else None
    return callback


@pytest.mark.asyncio
async def test_add_bot_shows_usage_when_token_missing():
    """When /add_bot is sent without a token, the handler explains the syntax."""

    message = build_message()
    manager = AsyncMock()
    command = build_command_args(None)

    await handle_add_bot(message, command, manager, "upd-1")

    message.answer.assert_awaited_once_with(token_command_usage("add_bot"))


@pytest.mark.asyncio
async def test_add_bot_rejects_when_registration_is_disabled_without_token():
    """
    When registration is disabled and the command has no token,
    the handler only reports closure (no delete).
    """

    message = build_message()
    manager = AsyncMock()
    command = build_command_args(None)

    with patch(
        "friends_bot_service.handlers.master.add_bot.settings.REGISTRATION_ENABLED",
        False,
    ):
        await handle_add_bot(message, command, manager, "upd-1")

    message.answer.assert_awaited_once_with(BOT_REGISTRATION_DISABLED)


@pytest.mark.asyncio
async def test_add_bot_rejects_when_registration_disabled_deletes_token_message():
    """
    When registration is disabled but a token was sent in the same message,
    the handler reports closure and removes the message from the chat.
    """

    message = build_message()
    manager = AsyncMock()
    command = build_command_args("123:secret")

    with (
        patch(
            "friends_bot_service.handlers.master.add_bot.settings.REGISTRATION_ENABLED",
            False,
        ),
        patch(
            "friends_bot_service.handlers.master.add_bot.try_delete_token_message",
            new=AsyncMock(),
        ) as try_delete_token_message_mock,
    ):
        await handle_add_bot(message, command, manager, "upd-1")

    message.answer.assert_awaited_once_with(BOT_REGISTRATION_DISABLED)
    try_delete_token_message_mock.assert_awaited_once_with(
        message,
        update_id="upd-1",
        flow="add_bot",
    )


@pytest.mark.asyncio
async def test_remove_bot_shows_usage_when_token_missing():
    """When /remove_bot is sent without a token, the handler explains the syntax."""

    message = build_message()
    manager = AsyncMock()
    command = build_command_args(None)

    await handle_remove_bot(message, command, manager, "upd-1")

    message.answer.assert_awaited_once_with(token_command_usage("remove_bot"))


@pytest.mark.asyncio
async def test_handle_add_bot_rejects_invalid_token_and_deletes_message():
    """
    Verify add-bot handling for an invalid token.

    Scenario:
    - /add_bot is called with a token
    - Bot.get_me raises TelegramUnauthorizedError

    Expected behavior:
    - the handler replies with the invalid-token message
    - database and manager calls are skipped
    - token cleanup helper is called in finally
    """

    message = build_message(user_id=20)
    command = build_command_args(" 123:invalid ")
    manager = AsyncMock()

    with (
        patch(
            "friends_bot_service.handlers.master.add_bot.Bot",
            return_value=FakeTempBot(
                get_me_exception=TelegramUnauthorizedError(
                    method=SimpleNamespace(__api_method__="getMe"),
                    message="unauthorized",
                )
            ),
        ),
        patch(
            "friends_bot_service.handlers.master.add_bot.run_with_unit_of_work",
            new=AsyncMock(side_effect=capture_uow_callback),
        ) as run_uow,
        patch(
            "friends_bot_service.handlers.master.add_bot.try_delete_token_message",
            new=AsyncMock(),
        ) as try_delete_token_message_mock,
    ):
        await handle_add_bot(message, command, manager, "upd-1")

    message.answer.assert_awaited_once_with(INVALID_BOT_TOKEN)
    run_uow.assert_not_awaited()
    manager.start_bot.assert_not_awaited()
    try_delete_token_message_mock.assert_awaited_once_with(
        message,
        update_id="upd-1",
        flow="add_bot",
    )


@pytest.mark.asyncio
async def test_handle_add_bot_registers_bot_and_reports_success():
    """
    Verify successful add-bot token handling.

    Scenario:
    - /add_bot is called with a valid token
    - token verification succeeds
    - bot registration and command sync succeed

    Expected behavior:
    - token is encrypted and saved
    - manager starts the bot
    - success message is sent
    - token cleanup helper is called in finally
    """

    message = build_message(user_id=20)
    command = build_command_args(" 123:valid-token ")
    manager = AsyncMock()
    manager.start_bot = AsyncMock(return_value=SimpleNamespace(id=999))
    bot_info = SimpleNamespace(id=999, username="new_bot")

    with (
        patch(
            "friends_bot_service.handlers.master.add_bot.Bot",
            return_value=FakeTempBot(bot_info=bot_info),
        ),
        patch(
            "friends_bot_service.handlers.master.add_bot._cipher.encrypt",
            return_value="encrypted-token",
        ) as encrypt_token_mock,
        patch(
            "friends_bot_service.handlers.master.add_bot.run_with_unit_of_work",
            new=AsyncMock(side_effect=capture_uow_callback),
        ) as run_uow,
        patch(
            "friends_bot_service.handlers.master.add_bot.sync_default_commands",
            new=AsyncMock(return_value=True),
        ) as sync_default_commands_mock,
        patch(
            "friends_bot_service.handlers.master.add_bot.try_delete_token_message",
            new=AsyncMock(),
        ) as try_delete_token_message_mock,
    ):
        await handle_add_bot(message, command, manager, "upd-1")

    encrypt_token_mock.assert_called_once_with("123:valid-token")
    run_uow.assert_awaited_once()
    uow = _last_uow["uow"]
    uow.bots.upsert.assert_awaited_once_with(
        bot_id=999,
        username="new_bot",
        encrypted_token="encrypted-token",
        owner_id=20,
    )
    uow.commit.assert_awaited_once()
    manager.start_bot.assert_awaited_once_with("123:valid-token")
    sync_default_commands_mock.assert_awaited_once()
    message.answer.assert_awaited_once_with(bot_registered_success("new_bot"))
    try_delete_token_message_mock.assert_awaited_once_with(
        message,
        update_id="upd-1",
        flow="add_bot",
    )


@pytest.mark.asyncio
async def test_handle_add_bot_reports_command_sync_failure_after_registration():
    """
    Verify add-bot flow when registration succeeds but command sync fails.

    Scenario:
    - token verification succeeds
    - bot is registered and started
    - command sync returns False

    Expected behavior:
    - the handler still reports successful registration
    - the answer also mentions deferred command sync
    """

    message = build_message(user_id=20)
    command = build_command_args("123:valid-token")
    manager = AsyncMock()
    manager.start_bot = AsyncMock(return_value=SimpleNamespace(id=999))
    bot_info = SimpleNamespace(id=999, username="new_bot")

    with (
        patch(
            "friends_bot_service.handlers.master.add_bot.Bot",
            return_value=FakeTempBot(bot_info=bot_info),
        ),
        patch(
            "friends_bot_service.handlers.master.add_bot._cipher.encrypt",
            return_value="encrypted-token",
        ),
        patch(
            "friends_bot_service.handlers.master.add_bot.run_with_unit_of_work",
            new=AsyncMock(side_effect=capture_uow_callback),
        ),
        patch(
            "friends_bot_service.handlers.master.add_bot.sync_default_commands",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "friends_bot_service.handlers.master.add_bot.try_delete_token_message",
            new=AsyncMock(),
        ),
    ):
        await handle_add_bot(message, command, manager, "upd-1")

    # The final answer must keep registration success and mention command sync retry.
    message.answer.assert_awaited_once_with(
        bot_registered_with_commands_warning("new_bot")
    )


@pytest.mark.asyncio
async def test_handle_remove_bot_rejects_invalid_token_and_deletes_message():
    """
    Verify remove-bot handling for an invalid token.

    Scenario:
    - /remove_bot is called with a token
    - Bot.get_me raises TelegramUnauthorizedError

    Expected behavior:
    - invalid-token message is sent
    - token cleanup helper is called in finally
    """

    message = build_message(user_id=20)
    command = build_command_args(" 123:invalid ")
    manager = AsyncMock()

    with (
        patch(
            "friends_bot_service.handlers.master.remove_bot.Bot",
            return_value=FakeTempBot(
                get_me_exception=TelegramUnauthorizedError(
                    method=SimpleNamespace(__api_method__="getMe"),
                    message="unauthorized",
                )
            ),
        ),
        patch(
            "friends_bot_service.handlers.master.remove_bot.run_with_unit_of_work",
            new=AsyncMock(side_effect=capture_uow_callback),
        ) as run_uow,
        patch(
            "friends_bot_service.handlers.master.remove_bot.try_delete_token_message",
            new=AsyncMock(),
        ) as try_delete_token_message_mock,
    ):
        await handle_remove_bot(message, command, manager, "upd-1")

    message.answer.assert_awaited_once_with(INVALID_BOT_TOKEN)
    manager.stop_bot.assert_not_awaited()
    run_uow.assert_not_awaited()
    try_delete_token_message_mock.assert_awaited_once_with(
        message,
        update_id="upd-1",
        flow="remove_bot",
    )


@pytest.mark.asyncio
async def test_handle_remove_bot_rolls_back_when_bot_is_not_deactivated():
    """
    Verify remove-bot flow when the bot cannot be deactivated for this owner.

    Scenario:
    - token verification succeeds
    - deactivate_bot_for_owner returns False

    Expected behavior:
    - the session is rolled back
    - failure message is sent
    """

    message = build_message(user_id=20)
    command = build_command_args("123:valid-token")
    manager = AsyncMock()
    bot_info = SimpleNamespace(id=999, username="owned_bot")

    with (
        patch(
            "friends_bot_service.handlers.master.remove_bot.Bot",
            return_value=FakeTempBot(bot_info=bot_info),
        ),
        patch(
            "friends_bot_service.handlers.master.remove_bot.run_with_unit_of_work",
            new=AsyncMock(side_effect=capture_remove_bot_not_deactivated),
        ),
        patch(
            "friends_bot_service.handlers.master.remove_bot.try_delete_token_message",
            new=AsyncMock(),
        ),
    ):
        await handle_remove_bot(message, command, manager, "upd-1")

    uow = _last_uow["uow"]
    uow.bots.deactivate_for_owner.assert_awaited_once_with(999, 20)
    uow.rollback.assert_awaited_once()
    manager.stop_bot.assert_not_awaited()
    message.answer.assert_awaited_once_with(REMOVE_BOT_NOT_FOUND)


@pytest.mark.asyncio
async def test_handle_remove_bot_deactivates_bot_and_stops_manager():
    """
    Verify successful remove-bot handling.

    Scenario:
    - token verification succeeds
    - bot deactivation succeeds

    Expected behavior:
    - the session is committed
    - manager.stop_bot is called
    - success message is sent
    - token cleanup helper is called in finally
    """

    message = build_message(user_id=20)
    command = build_command_args("123:valid-token")
    manager = AsyncMock()
    bot_info = SimpleNamespace(id=999, username="owned_bot")

    with (
        patch(
            "friends_bot_service.handlers.master.remove_bot.Bot",
            return_value=FakeTempBot(bot_info=bot_info),
        ),
        patch(
            "friends_bot_service.handlers.master.remove_bot.run_with_unit_of_work",
            new=AsyncMock(side_effect=capture_remove_bot_deactivated),
        ),
        patch(
            "friends_bot_service.handlers.master.remove_bot.try_delete_token_message",
            new=AsyncMock(),
        ) as try_delete_token_message_mock,
    ):
        await handle_remove_bot(message, command, manager, "upd-1")

    uow = _last_uow["uow"]
    uow.bots.deactivate_for_owner.assert_awaited_once_with(999, 20)
    uow.commit.assert_awaited_once()
    manager.stop_bot.assert_awaited_once_with(999)
    message.answer.assert_awaited_once_with(bot_removed_success("owned_bot"))
    try_delete_token_message_mock.assert_awaited_once_with(
        message,
        update_id="upd-1",
        flow="remove_bot",
    )


def test_get_bot_name_formats_username():
    """
    Verify formatting of bot display names.

    Scenario:
    - a registered bot object has a username

    Expected behavior:
    - the helper returns @username format
    """

    # Prepare a registered bot object.
    registered_bot = build_registered_bot(1, "test_bot")

    # The helper must prefix the username with @.
    assert get_bot_name(registered_bot) == "@test_bot"


def test_build_set_default_commands_keyboard_contains_bot_and_bulk_buttons():
    """
    Verify keyboard construction for multiple bot command sync.

    Scenario:
    - two registered bots are available for selection

    Expected behavior:
    - the keyboard contains one button per bot
    - the keyboard also contains the bulk update button
    """

    # Prepare two selectable bots.
    db_bots = [
        build_registered_bot(1, "first_bot"),
        build_registered_bot(2, "second_bot"),
    ]

    # Build the selection keyboard.
    keyboard = build_set_default_commands_keyboard(db_bots)
    button_texts = [button.text for row in keyboard.inline_keyboard for button in row]

    # The keyboard must contain both bot buttons and the bulk-update button.
    assert "@first_bot" in button_texts
    assert "@second_bot" in button_texts
    assert "Обновить у всех" in button_texts


@pytest.mark.asyncio
async def test_edit_callback_message_updates_message_when_present():
    """
    Verify callback message editing helper when callback.message exists.

    Scenario:
    - callback query contains an attached message

    Expected behavior:
    - the helper edits that message text
    """

    # Prepare a callback query with an editable message.
    callback = build_callback(with_message=True)

    # Run the helper.
    await edit_callback_message(callback, "Updated text")

    # The helper must edit the callback message.
    callback.message.edit_text.assert_awaited_once_with("Updated text")


@pytest.mark.asyncio
async def test_edit_callback_message_ignores_missing_message():
    """
    Verify callback message editing helper when callback.message is missing.

    Scenario:
    - callback query has no attached message

    Expected behavior:
    - the helper exits without raising
    """

    # Prepare a callback query without a message object.
    callback = build_callback(with_message=False)

    # The helper must quietly do nothing.
    await edit_callback_message(callback, "Updated text")


@pytest.mark.asyncio
async def test_set_default_commands_returns_early_when_user_is_missing():
    """
    Verify /set_default_commands early-exit branch when from_user is missing.

    Scenario:
    - the command handler is called
    - the incoming message has no from_user

    Expected behavior:
    - repository lookup is not called
    - no response message is sent
    """

    # Prepare a message without Telegram user data.
    message = build_message(user_id=None)

    with patch(
        "friends_bot_service.handlers.master.set_default_commands.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ) as run_uow:
        await set_default_commands(message, "upd-1")

    run_uow.assert_not_awaited()
    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_default_commands_reports_when_owner_has_no_bots():
    """
    Verify /set_default_commands behavior when the owner has no connected bots.

    Scenario:
    - repository returns an empty bot list for the owner

    Expected behavior:
    - the handler answers with the no-bots message
    """

    # Prepare a normal command request.
    message = build_message(user_id=20)

    with patch(
        "friends_bot_service.handlers.master.set_default_commands.run_with_unit_of_work",
        new=AsyncMock(return_value=[]),
    ):
        await set_default_commands(message, "upd-1")

    # The handler must answer with the no-bots text.
    message.answer.assert_awaited_once_with(NO_BOTS_FOR_COMMAND_SYNC)


@pytest.mark.asyncio
async def test_set_default_commands_updates_single_bot_immediately():
    """
    Verify /set_default_commands single-bot flow.

    Scenario:
    - repository returns exactly one active bot
    - command sync succeeds

    Expected behavior:
    - sync is executed immediately
    - success message for that bot is sent
    """

    # Prepare a normal command request with one connected bot.
    message = build_message(user_id=20)
    registered_bot = build_registered_bot(1, "single_bot")

    with (
        patch(
            "friends_bot_service.handlers.master.set_default_commands.run_with_unit_of_work",
            new=AsyncMock(return_value=[registered_bot]),
        ),
        patch(
            "friends_bot_service.handlers.master.set_default_commands.sync_commands_for_bot",
            new=AsyncMock(return_value=True),
        ) as sync_commands_for_bot,
    ):
        await set_default_commands(message, "upd-1")

    # The handler must sync immediately and answer with the success text.
    sync_commands_for_bot.assert_awaited_once_with(registered_bot)
    message.answer.assert_awaited_once_with(commands_updated_for_bot("@single_bot"))


@pytest.mark.asyncio
async def test_set_default_commands_shows_keyboard_for_multiple_bots():
    """
    Verify /set_default_commands multi-bot selection flow.

    Scenario:
    - repository returns multiple active bots for the owner

    Expected behavior:
    - the handler sends a selection message
    - inline keyboard is attached
    """

    # Prepare a normal command request with multiple connected bots.
    message = build_message(user_id=20)
    db_bots = [
        build_registered_bot(1, "first_bot"),
        build_registered_bot(2, "second_bot"),
    ]

    with patch(
        "friends_bot_service.handlers.master.set_default_commands.run_with_unit_of_work",
        new=AsyncMock(return_value=db_bots),
    ):
        await set_default_commands(message, "upd-1")

    # The handler must send the selection prompt with an inline keyboard.
    assert message.answer.await_count == 1
    assert (
        message.answer.await_args.args[0] == CHOOSE_BOT_FOR_COMMAND_SYNC
    )
    assert message.answer.await_args.kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_set_default_commands_for_selected_bot_rejects_invalid_callback_data():
    """
    Verify selected-bot callback handling for malformed callback data.

    Scenario:
    - callback data cannot be parsed into bot_id

    Expected behavior:
    - the handler answers with an alert about invalid bot selection
    """

    # Prepare a callback with malformed bot id.
    callback = build_callback(
        user_id=20,
        data="set_default_commands:bot:not-an-int",
    )

    await set_default_commands_for_selected_bot(callback, "upd-1")

    # The handler must answer with the invalid-bot alert.
    callback.answer.assert_awaited_once_with(CALLBACK_INVALID_BOT, show_alert=True)


@pytest.mark.asyncio
async def test_set_default_commands_for_selected_bot_rejects_unavailable_bot():
    """
    Verify selected-bot callback handling for inaccessible bots.

    Scenario:
    - callback data is valid
    - repository returns no active bot for this owner and bot_id

    Expected behavior:
    - the handler answers with an access-denied alert
    """

    # Prepare a callback pointing to an inaccessible bot.
    callback = build_callback(user_id=20, data="set_default_commands:bot:1")

    async def capture_no_owner_bot(callback):
        uow = AsyncMock()
        uow.bots = AsyncMock()
        uow.bots.get_active_for_owner = AsyncMock(return_value=None)
        return await callback(uow)

    with patch(
        "friends_bot_service.handlers.master.set_default_commands.run_with_unit_of_work",
        new=AsyncMock(side_effect=capture_no_owner_bot),
    ):
        await set_default_commands_for_selected_bot(callback, "upd-1")

    # The handler must answer with the unavailable-bot alert.
    callback.answer.assert_awaited_once_with(CALLBACK_BOT_NOT_OWNED, show_alert=True)


@pytest.mark.asyncio
async def test_set_default_commands_for_selected_bot_edits_success_message():
    """
    Verify selected-bot callback success flow.

    Scenario:
    - repository returns the selected active bot
    - command sync succeeds

    Expected behavior:
    - callback is acknowledged
    - result message is edited to the success text
    """

    # Prepare a callback pointing to a valid bot.
    callback = build_callback(user_id=20, data="set_default_commands:bot:1")
    registered_bot = build_registered_bot(1, "selected_bot")

    uow = AsyncMock()
    uow.bots = AsyncMock()

    async def capture_owner_bot(callback):
        uow = AsyncMock()
        uow.bots = AsyncMock()
        uow.bots.get_active_for_owner = AsyncMock(return_value=registered_bot)
        return await callback(uow)

    with (
        patch(
            "friends_bot_service.handlers.master.set_default_commands.run_with_unit_of_work",
            new=AsyncMock(side_effect=capture_owner_bot),
        ),
        patch(
            "friends_bot_service.handlers.master.set_default_commands.sync_commands_for_bot",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "friends_bot_service.handlers.master.set_default_commands.edit_callback_message",
            new=AsyncMock(),
        ) as edit_callback_message_mock,
    ):
        await set_default_commands_for_selected_bot(callback, "upd-1")

    # The handler must acknowledge the callback and
    # replace the message with success text.
    callback.answer.assert_awaited_once_with()
    edit_callback_message_mock.assert_awaited_once_with(
        callback,
        commands_updated_for_bot("@selected_bot"),
    )


@pytest.mark.asyncio
async def test_set_default_commands_for_all_bots_reports_partial_failures():
    """
    Verify bulk callback flow when some bot command syncs fail.

    Scenario:
    - repository returns multiple active bots
    - one sync succeeds and one sync fails

    Expected behavior:
    - callback is acknowledged
    - result message is edited with the failed bot list
    """

    # Prepare a bulk callback with two connected bots.
    callback = build_callback(user_id=20, data="set_default_commands:all")
    first_bot = build_registered_bot(1, "first_bot")
    second_bot = build_registered_bot(2, "second_bot")

    with (
        patch(
            "friends_bot_service.handlers.master.set_default_commands.run_with_unit_of_work",
            new=AsyncMock(return_value=[first_bot, second_bot]),
        ),
        patch(
            "friends_bot_service.handlers.master.set_default_commands.sync_commands_for_bot",
            new=AsyncMock(side_effect=[True, False]),
        ),
        patch(
            "friends_bot_service.handlers.master.set_default_commands.edit_callback_message",
            new=AsyncMock(),
        ) as edit_callback_message_mock,
    ):
        await set_default_commands_for_all_bots(callback, "upd-1")

    # The handler must acknowledge the callback and show the failed bot list.
    callback.answer.assert_awaited_once_with()
    edit_callback_message_mock.assert_awaited_once_with(
        callback,
        commands_bulk_failure(["@second_bot"]),
    )
