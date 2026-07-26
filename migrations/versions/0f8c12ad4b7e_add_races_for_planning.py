"""add races for planning

Revision ID: 0f8c12ad4b7e
Revises: 6cdb9cad41e0
Create Date: 2026-07-26 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0f8c12ad4b7e"
down_revision: Union[str, Sequence[str], None] = "6cdb9cad41e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the local table for athlete-confirmed future race goals."""

    op.create_table(
        "races",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sport_type", sa.String(length=20), nullable=False),
        sa.Column("race_date", sa.Date(), nullable=False),
        sa.Column("distance_meters", sa.Float(), nullable=False),
        sa.Column("priority", sa.String(length=1), nullable=False),
        sa.Column("desired_time_seconds", sa.Integer(), nullable=True),
        sa.Column("taper_override", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Remove the J1 race configuration table."""

    op.drop_table("races")
