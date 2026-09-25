"""Auditable mapping between one Pace session and one Garmin workout."""

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pace.database.models.base import Base, TimestampMixin


class GarminWorkoutExport(TimestampMixin, Base):
    """One explicitly confirmed Garmin upload/schedule operation."""

    __tablename__ = "garmin_workout_exports"
    __table_args__ = (
        UniqueConstraint(
            "planned_session_id",
            name="uq_garmin_workout_exports_planned_session_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    planned_session_id: Mapped[int] = mapped_column(
        ForeignKey("planned_sessions.id", ondelete="CASCADE"), nullable=False
    )
    garmin_workout_id: Mapped[str] = mapped_column(String(100), nullable=False)
    garmin_schedule_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    workout_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    pushed_to_device: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
