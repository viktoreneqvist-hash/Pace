"""Persistence operations for explicit upcoming race goals."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from pace.database.models import Race


def create_race(session: Session, race: Race) -> Race:
    """Store one athlete-confirmed race objective."""

    session.add(race)
    session.flush()
    return race


def get_race_by_id(session: Session, race_id: int) -> Race | None:
    """Return one race by its local identifier."""

    return session.get(Race, race_id)


def get_upcoming_races(session: Session, *, as_of_date: date) -> list[Race]:
    """Return current and future races in calendar order."""

    statement = (
        select(Race)
        .where(Race.race_date >= as_of_date)
        .order_by(Race.race_date, Race.id)
    )
    return list(session.scalars(statement))


def get_races(
    session: Session,
    *,
    as_of_date: date,
    include_past: bool,
) -> list[Race]:
    """Return races in calendar order, optionally including historical objectives."""

    statement = select(Race).order_by(Race.race_date, Race.id)
    if not include_past:
        statement = statement.where(Race.race_date >= as_of_date)
    return list(session.scalars(statement))
