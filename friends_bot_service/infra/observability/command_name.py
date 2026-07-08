def command_name_from_message_text(text: str | None) -> str:
    """Return the slash-command, stripping the variable @bot mention
    in chat to reduce cardinality (low-cardinality).
    """

    if text is None or not text.startswith("/"):
        return "non_command"

    command_token = text.split(maxsplit=1)[0]
    command = command_token.split("@", maxsplit=1)[0].lower()
    return command if command else "non_command"
