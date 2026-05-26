from types import SimpleNamespace
from unittest.mock import patch

import pytest
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError

from friends_bot_service.master_bot.usecases.verify_bot_token import (
    VerifiedBotInfo,
    VerifyBotTokenOutcome,
    verify_bot_token,
)
from tests.usecases.master_bot.helpers import FakeTempBot


@pytest.mark.asyncio
async def test_verify_bot_token_returns_network_error():
    with patch(
        "friends_bot_service.master_bot.usecases.verify_bot_token.Bot",
        return_value=FakeTempBot(
            get_me_exception=TelegramNetworkError(method=None, message="network")
        ),
    ):
        outcome, info = await verify_bot_token("123:token")

    assert outcome is VerifyBotTokenOutcome.NETWORK_ERROR
    assert info is None


@pytest.mark.asyncio
async def test_verify_bot_token_returns_invalid_token():
    with patch(
        "friends_bot_service.master_bot.usecases.verify_bot_token.Bot",
        return_value=FakeTempBot(
            get_me_exception=TelegramUnauthorizedError(
                method=SimpleNamespace(__api_method__="getMe"),
                message="unauthorized",
            )
        ),
    ):
        outcome, info = await verify_bot_token("123:token")

    assert outcome is VerifyBotTokenOutcome.INVALID_TOKEN
    assert info is None


@pytest.mark.asyncio
async def test_verify_bot_token_returns_unexpected_on_unknown_error():
    with patch(
        "friends_bot_service.master_bot.usecases.verify_bot_token.Bot",
        return_value=FakeTempBot(get_me_exception=RuntimeError("boom")),
    ):
        outcome, info = await verify_bot_token("123:token")

    assert outcome is VerifyBotTokenOutcome.UNEXPECTED
    assert info is None


@pytest.mark.asyncio
async def test_verify_bot_token_returns_username_missing():
    with patch(
        "friends_bot_service.master_bot.usecases.verify_bot_token.Bot",
        return_value=FakeTempBot(
            bot_info=SimpleNamespace(id=99, username=None),
        ),
    ):
        outcome, info = await verify_bot_token("123:token")

    assert outcome is VerifyBotTokenOutcome.USERNAME_MISSING
    assert info is None


@pytest.mark.asyncio
async def test_verify_bot_token_returns_success_with_bot_info():
    with patch(
        "friends_bot_service.master_bot.usecases.verify_bot_token.Bot",
        return_value=FakeTempBot(
            bot_info=SimpleNamespace(id=99, username="game_bot"),
        ),
    ):
        outcome, info = await verify_bot_token("123:token")

    assert outcome is VerifyBotTokenOutcome.SUCCESS
    assert info == VerifiedBotInfo(bot_id=99, username="game_bot")
