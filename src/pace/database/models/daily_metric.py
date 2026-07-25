"""Daily recovery and health metric persistence model."""

from datetime import date
from typing import Any

from sqlalchemy import Date, Float, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pace.database.models.base import Base, TimestampMixin


class DailyMetric(TimestampMixin, Base):
    """Garmin recovery and health signals for one calendar day."""

    __tablename__ = "daily_metrics"
    __table_args__ = (UniqueConstraint("date", name="uq_daily_metrics_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)

    hrv_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    hrv_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resting_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)

    sleep_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    average_stress: Mapped[float | None] = mapped_column(Float, nullable=True)
    body_battery_high: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body_battery_low: Mapped[int | None] = mapped_column(Integer, nullable=True)
    training_readiness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recovery_time_hours: Mapped[float | None] = mapped_column(Float, nullable=True)

    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
