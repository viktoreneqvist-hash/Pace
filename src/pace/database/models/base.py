"""Shared SQLAlchemy model base."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all Pace database models."""
