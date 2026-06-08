"""rename legacy draw tables and columns

Revision ID: a7f3c2d91e04
Revises: 8c4e1a9b2d10
Create Date: 2026-06-07 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "a7f3c2d91e04"
down_revision: Union[str, Sequence[str], None] = "8c4e1a9b2d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("players", "draw_entrants")
    op.rename_table("stats", "draw_stats")
    op.alter_column("chat_draw_claims", "game_type", new_column_name="draw_type")
    op.drop_index(op.f("ix_bots_last_game_attempt_at"), table_name="bots")
    op.alter_column(
        "bots",
        "last_game_attempt_at",
        new_column_name="last_draw_attempt_at",
    )
    op.create_index(
        op.f("ix_bots_last_draw_attempt_at"),
        "bots",
        ["last_draw_attempt_at"],
        unique=False,
    )
    op.execute("ALTER INDEX ix_stats_winner_top RENAME TO ix_draw_stats_winner_top")
    op.execute("ALTER INDEX ix_stats_loser_top RENAME TO ix_draw_stats_loser_top")


def downgrade() -> None:
    op.execute("ALTER INDEX ix_draw_stats_loser_top RENAME TO ix_stats_loser_top")
    op.execute("ALTER INDEX ix_draw_stats_winner_top RENAME TO ix_stats_winner_top")
    op.drop_index(op.f("ix_bots_last_draw_attempt_at"), table_name="bots")
    op.alter_column(
        "bots",
        "last_draw_attempt_at",
        new_column_name="last_game_attempt_at",
    )
    op.create_index(
        op.f("ix_bots_last_game_attempt_at"),
        "bots",
        ["last_game_attempt_at"],
        unique=False,
    )
    op.alter_column("chat_draw_claims", "draw_type", new_column_name="game_type")
    op.rename_table("draw_stats", "stats")
    op.rename_table("draw_entrants", "players")
