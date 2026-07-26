"""add structured planned-session heart-rate zone

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-26 17:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Keep the zone number machine-checkable rather than parsing AI prose."""

    with op.batch_alter_table("planned_sessions") as batch_op:
        batch_op.add_column(sa.Column("intensity_zone", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("planned_sessions") as batch_op:
        batch_op.drop_column("intensity_zone")
