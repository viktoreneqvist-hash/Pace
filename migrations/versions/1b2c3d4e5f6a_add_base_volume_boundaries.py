"""add athlete base-volume boundaries

Revision ID: 1b2c3d4e5f6a
Revises: 0a1b2c3d4e5f
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1b2c3d4e5f6a"
down_revision: Union[str, Sequence[str], None] = "0a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("training_preferences") as batch_op:
        batch_op.add_column(
            sa.Column("base_running_distance_ceiling_km", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("base_cycling_duration_ceiling_hours", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("base_total_duration_ceiling_hours", sa.Float(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("training_preferences") as batch_op:
        batch_op.drop_column("base_total_duration_ceiling_hours")
        batch_op.drop_column("base_cycling_duration_ceiling_hours")
        batch_op.drop_column("base_running_distance_ceiling_km")
