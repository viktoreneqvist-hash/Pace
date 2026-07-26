"""Persistence operations for athlete context events."""

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from pace.database.models import ContextEvent


def create_context_event(session: Session, context_event: ContextEvent) -> ContextEvent:
    """Store a new athlete-provided context event."""

    session.add(context_event)
    session.flush()
    return context_event


def get_context_events_for_date(
    session: Session,
    target_date: date,
) -> list[ContextEvent]:
    """Return context events that overlap a specific date."""

    statement = (
        select(ContextEvent)
        .where(
            ContextEvent.start_date <= target_date,
            or_(ContextEvent.end_date.is_(None), ContextEvent.end_date >= target_date),
        )
        .order_by(ContextEvent.start_date)
    )
    return list(session.scalars(statement))


def get_context_events_in_date_range(
    session: Session,
    *,
    start_date: date,
    end_date: date,
) -> list[ContextEvent]:
    """Return events that overlap an inclusive calendar-date window."""

    if end_date < start_date:
        raise ValueError("end_date cannot be earlier than start_date.")

    statement = (
        select(ContextEvent)
        .where(
            ContextEvent.start_date <= end_date,
            or_(ContextEvent.end_date.is_(None), ContextEvent.end_date >= start_date),
        )
        .order_by(ContextEvent.start_date, ContextEvent.id)
    )
    return list(session.scalars(statement))


def get_all_context_events(session: Session) -> list[ContextEvent]:
    """Return every stored event in chronological order."""

    statement = select(ContextEvent).order_by(ContextEvent.start_date, ContextEvent.id)
    return list(session.scalars(statement))
