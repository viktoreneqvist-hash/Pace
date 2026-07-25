"""Athlete-provided context persistence model."""

from datetime import date

from sqlalchemy import Date, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pace.database.models.base import Base, TimestampMixin


class ContextEvent(TimestampMixin, Base):
    """A structured event Garmin cannot observe directly."""

    __tablename__ = "context_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    affected_metrics: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
