"""Athlete-confirmed links from observed Garmin activities to race evidence."""

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pace.database.models.base import Base, TimestampMixin


class PerformanceEvidence(TimestampMixin, Base):
    """A future-extensible evidence record without self-reported performance data."""

    __tablename__ = "performance_evidence"
    __table_args__ = (
        UniqueConstraint("activity_id", name="uq_performance_evidence_activity_id"),
        UniqueConstraint("race_id", name="uq_performance_evidence_race_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(20), nullable=False)
    race_id: Mapped[int | None] = mapped_column(ForeignKey("races.id"), nullable=True)
    benchmark_protocol: Mapped[str | None] = mapped_column(String(100), nullable=True)
