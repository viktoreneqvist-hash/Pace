"""Privacy-minimized detailed Garmin facts for one normalized activity."""

from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pace.database.models.base import Base, TimestampMixin


class ActivityPerformanceDetail(TimestampMixin, Base):
    """Selected detail and split facts, never Garmin route or stream payloads."""

    __tablename__ = "activity_performance_details"
    __table_args__ = (
        UniqueConstraint(
            "activity_id",
            name="uq_activity_performance_details_activity_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id"), nullable=False
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maximum_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    average_speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_cadence: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_power: Mapped[float | None] = mapped_column(Float, nullable=True)
    splits: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    heart_rate_zones: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
