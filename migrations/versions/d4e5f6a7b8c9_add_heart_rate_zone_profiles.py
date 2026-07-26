"""add athlete-confirmed heart rate zone profiles

Revision ID: d4e5f6a7b8c9
Revises: c3e4f5a6b7d8
Create Date: 2026-07-26 17:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3e4f5a6b7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "heart_rate_zone_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sport_type", sa.String(length=20), nullable=False),
        sa.Column("zones", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sport_type", name="uq_hr_zone_profiles_sport"),
    )


def downgrade() -> None:
    op.drop_table("heart_rate_zone_profiles")
