import pytest

from friends_bot_service.middlewares.logging import redact_message_text_for_log


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/add_bot", "/add_bot"),
        ("/add_bot ", "/add_bot"),
        ("/add_bot 123:SECRET", "/add_bot"),
        ("/add_bot@mybot", "/add_bot"),
        ("/add_bot@mybot 1:2", "/add_bot"),
        ("/remove_bot", "/remove_bot"),
        ("/remove_bot\t", "/remove_bot"),
        ("/remove_bot x:y", "/remove_bot"),
        ("/remove_bot@bot", "/remove_bot"),
        ("/stats", "/stats"),
        ("plain text", "plain text"),
        ("", ""),
    ],
)
def test_redact_message_text_for_log(text: str, expected: str) -> None:
    assert redact_message_text_for_log(text) == expected
