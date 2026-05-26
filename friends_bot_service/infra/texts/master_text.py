BOT_REGISTRATION_DISABLED = "Регистрация ботов временно закрыта."
BOT_TOKEN_VERIFY_FAILED = "❌ Ошибка: не удалось верифицировать токен."
BOT_TOKEN_CHECK_FAILED = "❌ Ошибка: не удалось проверить токен."
BOT_USERNAME_MISSING = "❌ Ошибка: у бота отсутствует username."
COMMANDS_SYNC_FAILED_TRY_LATER = (
    "Команды обновить не удалось. Попробуй /set_default_commands позже."
)

COMMANDS_UPDATE_FAILED = "Не удалось обновить команды. Попробуй позже."
NO_BOTS_FOR_COMMAND_SYNC = "У тебя пока нет подключённых ботов для обновления команд."
NO_BOTS_FOR_COMMAND_SYNC_ALERT = "У тебя нет подключённых ботов для обновления команд."
CHOOSE_BOT_FOR_COMMAND_SYNC = (
    "Выбери бота, для которого нужно обновить команды, или обнови их у всех."
)
CALLBACK_USER_NOT_FOUND = "Не удалось определить пользователя."
CALLBACK_INVALID_BOT = "Некорректный бот."
CALLBACK_BOT_NOT_OWNED = "Этот бот недоступен для управления."
COMMANDS_UPDATED_ALL = "Команды обновлены у всех ботов."
REMOVE_BOT_NOT_FOUND = (
    "Не получилось отключить бота. Проверьте токен и что он был "
    "подключён с этого Telegram-аккаунта."
)


def token_command_usage(command: str) -> str:
    return (
        f"Отправьте одним сообщением: `/{command}` и токен через пробел. "
        "Токен выдаёт @BotFather."
    )


def bot_registered_success(username: str) -> str:
    return f"✅ Бот @{username} успешно зарегистрирован!"


def bot_registered_with_commands_warning(username: str) -> str:
    return f"{bot_registered_success(username)}\n{COMMANDS_SYNC_FAILED_TRY_LATER}"


def bot_removed_success(username: str) -> str:
    return f"Бот @{username} отключён от сервиса."


def commands_updated_for_bot(bot_name: str) -> str:
    return f"Команды для {bot_name} обновлены."


def commands_bulk_failure(failed_bot_names: list[str]) -> str:
    return "Не удалось обновить команды для:\n- " + "\n- ".join(failed_bot_names)
