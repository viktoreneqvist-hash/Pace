"""One local, athlete-confirmed planning preference profile."""

from typing import Any

from sqlalchemy import Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from pace.database.models.base import Base, TimestampMixin


class TrainingPreference(TimestampMixin, Base):
    """Availability and sport role, never self-reported performance capacity."""

    __tablename__ = "training_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sport_role: Mapped[str] = mapped_column(String(20), nullable=False)
    coaching_ambition: Mapped[str] = mapped_column(
        String(20), default="balanced", nullable=False
    )
    available_days: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    base_running_distance_ceiling_km: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    base_cycling_duration_ceiling_hours: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    base_total_duration_ceiling_hours: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
