"""Persistence model for an athlete's upcoming race goals."""

from datetime import date

from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from pace.database.models.base import Base, TimestampMixin


class Race(TimestampMixin, Base):
    """One explicitly configured upcoming race or event objective."""

    __tablename__ = "races"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sport_type: Mapped[str] = mapped_column(String(20), nullable=False)
    race_date: Mapped[date] = mapped_column(Date, nullable=False)
    distance_meters: Mapped[float] = mapped_column(Float, nullable=False)
    priority: Mapped[str] = mapped_column(String(1), nullable=False)
    desired_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    taper_override: Mapped[str | None] = mapped_column(String(20), nullable=True)
