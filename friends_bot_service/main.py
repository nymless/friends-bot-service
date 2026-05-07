import asyncio

from aiogram import Bot, Dispatcher

from friends_bot_service.config import BOT_TOKEN, DB_PATH
from friends_bot_service.database import DBHandler
from friends_bot_service.handlers import router


async def main():
    bot = Bot(token=BOT_TOKEN)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    db_handler = DBHandler(DB_PATH)

    await dispatcher.start_polling(bot, db=db_handler)


if __name__ == "__main__":
    asyncio.run(main())
