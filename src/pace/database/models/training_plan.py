"""Versioned, reviewable plan drafts and their structured sessions."""

from datetime import date
from typing import Any

from sqlalchemy import Date, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pace.database.models.base import Base, TimestampMixin


class TrainingPlan(TimestampMixin, Base):
    """A generated draft or accepted plan, never an overwritten history record."""

    __tablename__ = "training_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_plans.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    contract_version: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    goal_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    race_id: Mapped[int | None] = mapped_column(ForeignKey("races.id"), nullable=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    block_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    block_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    detailed_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    detailed_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    block_outline: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    coach_assessment: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class PlannedSession(TimestampMixin, Base):
    """One structured workout in a specific immutable plan version."""

    __tablename__ = "planned_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("training_plans.id"), nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    sport_type: Mapped[str] = mapped_column(String(20), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    distance_meters: Mapped[float | None] = mapped_column(nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intensity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    intensity_zone: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intensity_target: Mapped[str] = mapped_column(Text, nullable=False)
    heart_rate_zone: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class SessionFeedback(TimestampMixin, Base):
    """Athlete-confirmed session outcome; optional text stays local by default."""

    __tablename__ = "session_feedback"
    __table_args__ = (
        UniqueConstraint("planned_session_id", name="uq_session_feedback_planned_session"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    planned_session_id: Mapped[int] = mapped_column(
        ForeignKey("planned_sessions.id"), nullable=False
    )
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    share_note_with_ai: Mapped[bool] = mapped_column(default=False, nullable=False)
