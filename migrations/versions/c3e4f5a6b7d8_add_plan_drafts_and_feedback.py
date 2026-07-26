"""add reviewable plan drafts and session feedback

Revision ID: c3e4f5a6b7d8
Revises: b8d1e6a5c2f9
Create Date: 2026-07-26 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3e4f5a6b7d8"
down_revision: Union[str, Sequence[str], None] = "b8d1e6a5c2f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create local plan, preference, and feedback tables."""

    op.create_table(
        "training_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sport_role", sa.String(length=20), nullable=False),
        sa.Column("available_days", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "training_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_plan_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("goal_mode", sa.String(length=20), nullable=False),
        sa.Column("race_id", sa.Integer(), nullable=True),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("block_start_date", sa.Date(), nullable=False),
        sa.Column("block_end_date", sa.Date(), nullable=False),
        sa.Column("detailed_start_date", sa.Date(), nullable=False),
        sa.Column("detailed_end_date", sa.Date(), nullable=False),
        sa.Column("block_outline", sa.JSON(), nullable=False),
        sa.Column("context_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_plan_id"], ["training_plans.id"]),
        sa.ForeignKeyConstraint(["race_id"], ["races.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "planned_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("sport_type", sa.String(length=20), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("distance_meters", sa.Float(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("intensity_type", sa.String(length=20), nullable=False),
        sa.Column("intensity_target", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["training_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "session_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("planned_session_id", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("share_note_with_ai", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["planned_session_id"], ["planned_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("planned_session_id", name="uq_session_feedback_planned_session"),
    )


def downgrade() -> None:
    """Remove J3 local plan state."""

    op.drop_table("session_feedback")
    op.drop_table("planned_sessions")
    op.drop_table("training_plans")
    op.drop_table("training_preferences")
