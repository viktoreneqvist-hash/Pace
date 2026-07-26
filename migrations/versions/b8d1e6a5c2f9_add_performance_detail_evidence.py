"""add privacy-minimized performance detail and race evidence

Revision ID: b8d1e6a5c2f9
Revises: 0f8c12ad4b7e
Create Date: 2026-07-26 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8d1e6a5c2f9"
down_revision: Union[str, Sequence[str], None] = "0f8c12ad4b7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create bounded-detail, evidence, and audit tables."""

    op.create_table(
        "activity_performance_details",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("distance_meters", sa.Float(), nullable=True),
        sa.Column("average_heart_rate", sa.Integer(), nullable=True),
        sa.Column("maximum_heart_rate", sa.Integer(), nullable=True),
        sa.Column("average_speed_mps", sa.Float(), nullable=True),
        sa.Column("average_cadence", sa.Float(), nullable=True),
        sa.Column("average_power", sa.Float(), nullable=True),
        sa.Column("splits", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "activity_id", name="uq_activity_performance_details_activity_id"
        ),
    )
    op.create_table(
        "performance_sync_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("requested_start_date", sa.Date(), nullable=False),
        sa.Column("requested_end_date", sa.Date(), nullable=False),
        sa.Column("candidate_activities", sa.Integer(), nullable=False),
        sa.Column("details_fetched", sa.Integer(), nullable=False),
        sa.Column("details_inserted", sa.Integer(), nullable=False),
        sa.Column("details_updated", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "performance_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(length=20), nullable=False),
        sa.Column("race_id", sa.Integer(), nullable=True),
        sa.Column("benchmark_protocol", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"]),
        sa.ForeignKeyConstraint(["race_id"], ["races.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("activity_id", name="uq_performance_evidence_activity_id"),
        sa.UniqueConstraint("race_id", name="uq_performance_evidence_race_id"),
    )


def downgrade() -> None:
    """Remove J2B tables."""

    op.drop_table("performance_evidence")
    op.drop_table("performance_sync_runs")
    op.drop_table("activity_performance_details")
