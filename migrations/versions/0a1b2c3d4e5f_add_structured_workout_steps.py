"""add structured workout steps

Revision ID: 0a1b2c3d4e5f
Revises: f2a3b4c5d6e7
Create Date: 2026-07-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0a1b2c3d4e5f"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("planned_sessions") as batch:
        batch.add_column(sa.Column("workout_steps", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("planned_sessions") as batch:
        batch.drop_column("workout_steps")
