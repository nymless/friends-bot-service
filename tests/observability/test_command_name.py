from friends_bot_service.infra.observability.command_name import (
    command_name_from_message_text,
)


def test_command_name_from_plain_slash_command():
    assert command_name_from_message_text("/run") == "/run"


def test_command_name_strips_bot_username_suffix():
    assert command_name_from_message_text("/run@my_bot") == "/run"


def test_command_name_for_non_command():
    assert command_name_from_message_text("hello") == "non_command"
    assert command_name_from_message_text(None) == "non_command"
