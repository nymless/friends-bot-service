from unittest.mock import patch

from friends_bot_service.infra.telegram.bot_factory import create_bot


def test_create_bot_uses_default_api_when_base_url_unset() -> None:
    with patch("friends_bot_service.infra.telegram.bot_factory.settings") as settings:
        settings.TELEGRAM_API_BASE_URL = None
        bot = create_bot("1:AAtest")
    assert bot.session.api.is_local is False


def test_create_bot_uses_custom_api_base() -> None:
    with patch("friends_bot_service.infra.telegram.bot_factory.settings") as settings:
        settings.TELEGRAM_API_BASE_URL = "http://telegram-mock:8081"
        bot = create_bot("1000000:AAloadtestfake")
    assert bot.session.api.base == "http://telegram-mock:8081/bot{token}/{method}"
    assert bot.session.api.is_local is True
