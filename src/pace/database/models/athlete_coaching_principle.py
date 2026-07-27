"""Athlete-approved, reviewable coaching principles."""

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pace.database.models.base import Base, TimestampMixin


class AthleteCoachingPrinciple(TimestampMixin, Base):
    __tablename__ = "athlete_coaching_principles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    source_plan_id: Mapped[int] = mapped_column(ForeignKey("training_plans.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    review_due_date: Mapped[date] = mapped_column(Date, nullable=False)
