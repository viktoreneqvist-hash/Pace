"""remove legacy preference and add plan contract version

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-26 18:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove superseded frequency policy while preserving legacy plan rows."""

    with op.batch_alter_table("training_preferences") as batch_op:
        batch_op.drop_column("weekly_run_sessions")
    with op.batch_alter_table("training_plans") as batch_op:
        batch_op.add_column(
            sa.Column(
                "contract_version",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )
    with op.batch_alter_table("planned_sessions") as batch_op:
        batch_op.add_column(sa.Column("heart_rate_zone", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("target", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("training_plans") as batch_op:
        batch_op.drop_column("contract_version")
    with op.batch_alter_table("training_preferences") as batch_op:
        batch_op.add_column(sa.Column("weekly_run_sessions", sa.Integer(), nullable=True))
    with op.batch_alter_table("planned_sessions") as batch_op:
        batch_op.drop_column("target")
        batch_op.drop_column("heart_rate_zone")
