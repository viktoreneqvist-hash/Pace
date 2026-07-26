"""add coaching ambition preference

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-26 21:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Give existing athletes the explicit neutral coaching default."""

    with op.batch_alter_table("training_preferences") as batch_op:
        batch_op.add_column(
            sa.Column(
                "coaching_ambition",
                sa.String(length=20),
                nullable=False,
                server_default="balanced",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("training_preferences") as batch_op:
        batch_op.drop_column("coaching_ambition")
