"""Activity database model."""

from datetime import date

from sqlalchemy import Date, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pace.database.models.base import Base


class Activity(Base):
    """A normalized endurance activity."""

    __tablename__ = "activities"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "external_id",
            name="uq_activities_source_external_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    date: Mapped[date] = mapped_column(Date, nullable=False)

    sport_type: Mapped[str] = mapped_column(String, nullable=False)

    distance_km: Mapped[float] = mapped_column(Float, nullable=False)

    duration_s: Mapped[int] = mapped_column(Integer, nullable=False)

    average_hr: Mapped[int | None] = mapped_column(Integer, nullable=True)

    max_hr: Mapped[int | None] = mapped_column(Integer, nullable=True)

    elevation_gain_m: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    source: Mapped[str] = mapped_column(String, nullable=False)

    external_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
