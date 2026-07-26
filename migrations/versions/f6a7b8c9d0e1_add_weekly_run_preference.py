"""add explicit weekly run-session planning preference

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-26 17:25:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Existing preferences remain incomplete until the athlete chooses a count."""

    with op.batch_alter_table("training_preferences") as batch_op:
        batch_op.add_column(sa.Column("weekly_run_sessions", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("training_preferences") as batch_op:
        batch_op.drop_column("weekly_run_sessions")
