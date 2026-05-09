from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from friends_bot_service.core.config import settings

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
