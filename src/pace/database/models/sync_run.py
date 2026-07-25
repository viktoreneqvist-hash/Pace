"""Synchronization audit persistence model."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pace.database.models.base import Base, TimestampMixin, utc_now


class SyncRun(TimestampMixin, Base):
    """A record of one provider synchronization attempt."""

    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)

    requested_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    requested_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    activities_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    activities_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    activities_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    daily_metrics_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    daily_metrics_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    daily_metrics_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
