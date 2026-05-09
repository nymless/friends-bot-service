from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from friends_bot_service.models.base_model import Base


class Player(Base):
    """A player in the database."""

    __tablename__ = "players"

    bot_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
    )

    __table_args__ = (PrimaryKeyConstraint("bot_id", "chat_id", "user_id"),)


class GameStats(Base):
    """Game statistics for a player in the database."""

    __tablename__ = "stats"

    bot_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    win_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    last_win: Mapped[date | None] = mapped_column(Date, nullable=True)
    lose_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    last_lose: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("bot_id", "chat_id", "user_id"),
        # Database-level integrity protection:
        # one winner or loser per bot and chat each day
        UniqueConstraint("bot_id", "chat_id", "last_win", name="uq_bot_chat_win_day"),
        UniqueConstraint("bot_id", "chat_id", "last_lose", name="uq_bot_chat_lose_day"),
        # Indexes for fast leaderboard queries
        Index("ix_stats_winner_top", "bot_id", "chat_id", win_count.desc()),
        Index("ix_stats_loser_top", "bot_id", "chat_id", lose_count.desc()),
    )
