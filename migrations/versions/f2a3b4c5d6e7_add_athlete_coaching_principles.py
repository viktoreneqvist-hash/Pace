"""add athlete coaching principles

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table("athlete_coaching_principles", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("statement", sa.Text(), nullable=False), sa.Column("source_plan_id", sa.Integer(), sa.ForeignKey("training_plans.id"), nullable=False), sa.Column("status", sa.String(length=20), nullable=False), sa.Column("review_due_date", sa.Date(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))

def downgrade() -> None:
    op.drop_table("athlete_coaching_principles")
