import asyncio
import contextlib
import logging
import sys

from aiogram import Bot, Dispatcher
from fastapi import FastAPI

from friends_bot_service.bot_admin.interfaces import BotRuntimePort
from friends_bot_service.bot_admin.usecases import LoadActiveBots
from friends_bot_service.infra.api.app_state import WebhookAppState
from friends_bot_service.infra.api.webhook_handler import router
from friends_bot_service.infra.bootstrap import dispatchers
from friends_bot_service.infra.bootstrap.db import unit_of_work
from friends_bot_service.infra.bootstrap.master_polling import (
    MasterBotPollingContext,
    start_master_bot_polling,
)
from friends_bot_service.infra.bot_manager import factory as manager_factory
from friends_bot_service.infra.core.config import settings
from friends_bot_service.infra.enums.enums import BotMode
from friends_bot_service.infra.observability import (
    setup_webhook_observability,
    start_metrics_server,
)
from friends_bot_service.infra.security import default_token_cipher
from friends_bot_service.infra.telegram.bot_factory import create_bot

_logger = logging.getLogger(__name__)

_load_active_bots = LoadActiveBots(default_token_cipher())


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
    root_logger.addHandler(console_handler)


def create_master_runtime_components() -> tuple[Dispatcher, Bot]:
    """Builds runtime components for the master bot."""

    master_dp = dispatchers.get_master_bot_dispatcher()
    master_bot = create_bot(settings.MASTER_TOKEN)
    return master_dp, master_bot


def create_polling_runtime_components() -> tuple[BotRuntimePort, Dispatcher, Bot]:
    """Builds runtime components for polling mode."""

    manager = manager_factory.create_polling_bot_manager(dispatchers.get_bot_dispatcher)
    master_dp, master_bot = create_master_runtime_components()
    return manager, master_dp, master_bot


def create_webhook_runtime_components() -> tuple[
    Dispatcher, BotRuntimePort, Dispatcher, Bot
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


async def load_registered_bots(manager: BotRuntimePort) -> None:
    """Loads active bots from the database and starts them."""

    async with unit_of_work() as uow:
        result = await _load_active_bots.execute(uow.bots, manager)

    _logger.info("loading bots count=%s", result.started_count)


async def run_polling() -> None:
    """Runs the application in polling mode."""

    _logger.info("starting application mode=%s", settings.BOT_MODE)

    if settings.BOT_MODE == BotMode.WEBHOOK:
        _logger.critical("invalid mode for polling app, exiting")
        sys.exit(1)

    start_metrics_server(
        host=settings.METRICS_BIND_HOST,
        port=settings.METRICS_BIND_PORT,
    )
    _logger.info(
        "metrics server started host=%s port=%s",
        settings.METRICS_BIND_HOST,
        settings.METRICS_BIND_PORT,
    )

    manager, master_dp, master_bot = create_polling_runtime_components()
    master_context = MasterBotPollingContext(manager=manager)

    _logger.info("master bot initialized")
    await load_registered_bots(manager)

    try:
        await start_master_bot_polling(master_dp, master_bot, master_context)
    finally:
        _logger.warning("shutting down application")

        await manager.stop_all()
        await master_bot.session.close()

        _logger.info("shutdown completed")


def create_webhook_app() -> FastAPI:
    """Creates the FastAPI application for webhook mode."""

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        _logger.info("starting FastAPI app mode=%s", settings.BOT_MODE)

        if settings.BOT_MODE == BotMode.POLLING:
            _logger.critical("invalid mode for webhook app, exiting")
            sys.exit(1)

        start_metrics_server(
            host=settings.METRICS_BIND_HOST,
            port=settings.METRICS_BIND_PORT,
        )
        _logger.info(
            "metrics server started host=%s port=%s",
            settings.METRICS_BIND_HOST,
            settings.METRICS_BIND_PORT,
        )

        dp, manager, master_dp, master_bot = create_webhook_runtime_components()
        master_context = MasterBotPollingContext(manager=manager)

        webhook_secret_token = settings.WEBHOOK_SECRET_TOKEN
        assert webhook_secret_token is not None

        app.state = WebhookAppState(  # type: ignore[assignment]
            dp=dp,
            manager=manager,
            webhook_secret_token=webhook_secret_token,
            master_dp=master_dp,
            master_bot=master_bot,
        )

        _logger.info("master bot initialized")
        await load_registered_bots(manager)

        master_polling_task = asyncio.create_task(
            start_master_bot_polling(master_dp, master_bot, master_context)
        )

        _logger.info("master polling started")

        try:
            yield
        finally:
            _logger.warning("shutting down FastAPI app")

            master_polling_task.cancel()

            with contextlib.suppress(asyncio.CancelledError):
                await master_polling_task

            await manager.stop_all()
            await master_bot.session.close()

            _logger.info("shutdown completed")

    app = FastAPI(lifespan=lifespan)
    setup_webhook_observability(app)
    app.include_router(router)
    return app
