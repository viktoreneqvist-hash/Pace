"""add structured session feedback

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-07-27 15:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add optional athlete-reported exertion and reason without rewriting notes."""

    with op.batch_alter_table("session_feedback") as batch_op:
        batch_op.add_column(sa.Column("perceived_exertion", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("reason_code", sa.String(length=30), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("session_feedback") as batch_op:
        batch_op.drop_column("reason_code")
        batch_op.drop_column("perceived_exertion")
