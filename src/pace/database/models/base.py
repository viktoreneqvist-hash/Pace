"""Shared SQLAlchemy model primitives."""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Return the current time in UTC."""

    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base class for all Pace database models."""


class TimestampMixin:
    """Add audit timestamps to a database record."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
