"""One local, athlete-confirmed planning preference profile."""

from typing import Any

from sqlalchemy import Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from pace.database.models.base import Base, TimestampMixin


class TrainingPreference(TimestampMixin, Base):
    """Availability and sport role, never self-reported performance capacity."""

    __tablename__ = "training_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sport_role: Mapped[str] = mapped_column(String(20), nullable=False)
    available_days: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
