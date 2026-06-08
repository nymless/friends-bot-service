import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from friends_bot_service.infra.core.config import settings
from friends_bot_service.infra.enums.enums import BotMode

# Create an async engine for the database.
_engine = create_async_engine(
    settings.DB_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,
)

# Create a session factory for the database.
session_factory = async_sessionmaker(bind=_engine, expire_on_commit=False)


def worker_count_for_pool_budget() -> int:
    """Returns how many app processes each create their own SQLAlchemy pool."""

    if settings.BOT_MODE == BotMode.WEBHOOK:
        return settings.WORKER_COUNT
    return 1


def max_db_pool_connections() -> int:
    """Upper bound on DB connections opened by the running service."""

    per_worker_max = settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW
    return worker_count_for_pool_budget() * per_worker_max


def log_db_pool_budget(logger: logging.Logger) -> None:
    """Logs the configured SQLAlchemy connection budget at startup."""

    workers = worker_count_for_pool_budget()
    logger.info(
        (
            "database connection budget workers=%s pool_size=%s "
            "max_overflow=%s total_max=%s"
        ),
        workers,
        settings.DB_POOL_SIZE,
        settings.DB_MAX_OVERFLOW,
        max_db_pool_connections(),
    )
