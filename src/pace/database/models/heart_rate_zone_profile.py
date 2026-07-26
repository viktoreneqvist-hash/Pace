"""Athlete-confirmed Garmin heart-rate zone boundaries by sport."""

from typing import Any

from sqlalchemy import Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pace.database.models.base import Base, TimestampMixin


class HeartRateZoneProfile(TimestampMixin, Base):
    """Local zone facts; Pace never derives them from an observed maximum HR."""

    __tablename__ = "heart_rate_zone_profiles"
    __table_args__ = (UniqueConstraint("sport_type", name="uq_hr_zone_profiles_sport"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sport_type: Mapped[str] = mapped_column(String(20), nullable=False)
    zones: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
