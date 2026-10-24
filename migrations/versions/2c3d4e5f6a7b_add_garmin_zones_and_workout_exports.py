"""add Garmin heart-rate zones and workout export mappings

Revision ID: 2c3d4e5f6a7b
Revises: 1b2c3d4e5f6a
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2c3d4e5f6a7b"
down_revision: Union[str, Sequence[str], None] = "1b2c3d4e5f6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("activity_performance_details") as batch_op:
        batch_op.add_column(
            sa.Column(
                "heart_rate_zones",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )

    op.create_table(
        "garmin_workout_exports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("planned_session_id", sa.Integer(), nullable=False),
        sa.Column("garmin_workout_id", sa.String(length=100), nullable=False),
        sa.Column("garmin_schedule_id", sa.String(length=100), nullable=True),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("workout_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("pushed_to_device", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["planned_session_id"], ["planned_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "planned_session_id", name="uq_garmin_workout_exports_planned_session_id"
        ),
    )


def downgrade() -> None:
    op.drop_table("garmin_workout_exports")
    with op.batch_alter_table("activity_performance_details") as batch_op:
        batch_op.drop_column("heart_rate_zones")
