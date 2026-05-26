from aiogram.types import BotCommand

BOT_COMMANDS = [
    BotCommand(command="reg", description="Присоединиться к игре"),
    BotCommand(command="delete", description="Выйти из игры"),
    BotCommand(command="list", description="Кто участвует в игре"),
    BotCommand(command="run", description="Выбрать юзера дня"),
    BotCommand(command="loser", description="Выбрать лузера дня"),
    BotCommand(command="stats", description="Показать рейтинг юзеров дня"),
    BotCommand(command="loserstats", description="Показать рейтинг лузеров дня"),
]
