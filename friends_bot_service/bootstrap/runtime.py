import asyncio
import contextlib
import logging
import sys

from aiogram import Bot, Dispatcher
from fastapi import FastAPI
from sqlalchemy import select

from friends_bot_service.api.webhook_handler import router
from friends_bot_service.bootstrap import dispatchers
from friends_bot_service.bot_manager import factory as manager_factory
from friends_bot_service.bot_manager.base import BotManager
from friends_bot_service.core.config import settings
from friends_bot_service.core.database import session_factory
from friends_bot_service.core.security import decrypt_token
from friends_bot_service.enums.enums import BotMode
from friends_bot_service.models.bot_models import RegisteredBot

logger = logging.getLogger(__name__)


class PackagePathFilter(logging.Filter):
    def filter(self, record):
        prefix = "friends_bot_service."
        if record.name.startswith(prefix):
            record.name = record.name[len(prefix) :]
        return True


def setup_logging() -> None:
    """Configures application logging."""

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    log_format = "%(asctime)s | %(levelname)-8s | %(name)-22s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(log_format, datefmt=date_format)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(PackagePathFilter())
    root_logger.handlers = []
    root_logger.addHandler(console_handler)


def create_master_runtime_components() -> tuple[Dispatcher, Bot]:
    """Builds runtime components for the master bot."""

    master_dp = dispatchers.get_master_bot_dispatcher()
    master_bot = Bot(token=settings.MASTER_TOKEN)
    return master_dp, master_bot


def create_polling_runtime_components() -> tuple[BotManager, Dispatcher, Bot]:
    """Builds runtime components for polling mode."""

    manager = manager_factory.create_polling_bot_manager(dispatchers.get_bot_dispatcher)
    master_dp, master_bot = create_master_runtime_components()
    return manager, master_dp, master_bot


def create_webhook_runtime_components() -> tuple[
    Dispatcher, BotManager, Dispatcher, Bot
]:
    """Builds runtime components for webhook mode."""

    if settings.WEBHOOK_BASE_URL is None:
        raise ValueError("WEBHOOK_BASE_URL is required in webhook mode")
    if settings.WEBHOOK_SECRET_TOKEN is None:
        raise ValueError("WEBHOOK_SECRET_TOKEN is required in webhook mode")

    dp = dispatchers.get_bot_dispatcher()
    manager = manager_factory.create_webhook_bot_manager(
        settings.WEBHOOK_BASE_URL,
        settings.WEBHOOK_SECRET_TOKEN,
    )
    master_dp, master_bot = create_master_runtime_components()
    return dp, manager, master_dp, master_bot


async def load_registered_bots(manager: BotManager) -> None:
    """Loads active bots from the database and starts them."""

    async with session_factory() as session:
        result = await session.execute(
            select(RegisteredBot).where(RegisteredBot.is_active)
        )
        bots_to_load = result.scalars().all()

        logger.info("loading bots count=%s", len(bots_to_load))

        for bot_db in bots_to_load:
            token = decrypt_token(bot_db.encrypted_token)
            await manager.start_bot(token)

            logger.info(
                "bot started bot_id=%s username=%s",
                bot_db.bot_id,
                bot_db.username,
            )


async def run_polling() -> None:
    """Runs the application in polling mode."""

    logger.info("starting application mode=%s", settings.BOT_MODE)

    if settings.BOT_MODE == BotMode.WEBHOOK:
        logger.critical("invalid mode for polling app, exiting")
        sys.exit(1)

    manager, master_dp, master_bot = create_polling_runtime_components()

    logger.info("master bot initialized")
    await load_registered_bots(manager)

    try:
        await master_dp.start_polling(master_bot, manager=manager)
    finally:
        logger.warning("shutting down application")

        await manager.stop_all()
        await master_bot.session.close()

        logger.info("shutdown completed")


def create_webhook_app() -> FastAPI:
    """Creates the FastAPI application for webhook mode."""

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("starting FastAPI app mode=%s", settings.BOT_MODE)

        if settings.BOT_MODE == BotMode.POLLING:
            logger.critical("invalid mode for webhook app, exiting")
            sys.exit(1)

        dp, manager, master_dp, master_bot = create_webhook_runtime_components()

        app.state.dp = dp
        app.state.manager = manager
        app.state.webhook_secret_token = settings.WEBHOOK_SECRET_TOKEN
        app.state.master_dp = master_dp
        app.state.master_bot = master_bot

        logger.info("master bot initialized")
        await load_registered_bots(manager)

        master_polling_task = asyncio.create_task(master_dp.start_polling(master_bot))

        logger.info("master polling started")

        try:
            yield
        finally:
            logger.warning("shutting down FastAPI app")

            master_polling_task.cancel()

            with contextlib.suppress(asyncio.CancelledError):
                await master_polling_task

            await manager.stop_all()
            await master_bot.session.close()

            logger.info("shutdown completed")

    app = FastAPI(lifespan=lifespan)
    app.include_router(router)
    return app
