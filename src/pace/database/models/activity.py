"""Normalized activity persistence model."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pace.database.models.base import Base, TimestampMixin


class Activity(TimestampMixin, Base):
    """A normalized activity received from an external provider."""

    __tablename__ = "activities"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_activity_id",
            name="uq_activities_provider_activity_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_activity_id: Mapped[str] = mapped_column(String(100), nullable=False)

    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sport_type: Mapped[str] = mapped_column(String(50), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_gain_meters: Mapped[float | None] = mapped_column(Float, nullable=True)

    average_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maximum_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    average_speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_cadence: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_power: Mapped[float | None] = mapped_column(Float, nullable=True)
    training_effect_aerobic: Mapped[float | None] = mapped_column(Float, nullable=True)
    training_effect_anaerobic: Mapped[float | None] = mapped_column(Float, nullable=True)

    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
