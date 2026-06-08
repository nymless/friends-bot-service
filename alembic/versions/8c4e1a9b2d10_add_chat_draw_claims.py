"""add chat draw claims

Revision ID: 8c4e1a9b2d10
Revises: 2bb4438ada27
Create Date: 2026-06-07 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "8c4e1a9b2d10"
down_revision: Union[str, Sequence[str], None] = "2bb4438ada27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_draw_claims",
        sa.Column("bot_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("game_type", sa.String(), nullable=False),
        sa.Column("draw_date", sa.Date(), nullable=False),
        sa.Column("winner_user_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("bot_id", "chat_id", "game_type", "draw_date"),
    )


def downgrade() -> None:
    op.drop_table("chat_draw_claims")
