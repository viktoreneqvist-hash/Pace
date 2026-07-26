"""Audit model for a bounded Garmin performance-detail import."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pace.database.models.base import Base, TimestampMixin, utc_now


class PerformanceSyncRun(TimestampMixin, Base):
    """One attempt to import privacy-minimized activity details and splits."""

    __tablename__ = "performance_sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    requested_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    requested_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    candidate_activities: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    details_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    details_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    details_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
