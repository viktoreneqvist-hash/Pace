"""Persistence operations for explicit upcoming race goals."""

from datetime import date

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pace.database.models import PerformanceEvidence, Race, TrainingPlan


@dataclass(frozen=True, slots=True)
class RaceUsage:
    plan_count: int
    accepted_plan_count: int
    performance_evidence_count: int


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
        .where(Race.race_date >= as_of_date, Race.status == "active")
        .order_by(Race.race_date, Race.id)
    )
    return list(session.scalars(statement))


def get_races(
    session: Session,
    *,
    as_of_date: date,
    include_past: bool,
    include_cancelled: bool,
) -> list[Race]:
    """Return races in calendar order, optionally including historical objectives."""

    statement = select(Race).order_by(Race.race_date, Race.id)
    if not include_past:
        statement = statement.where(Race.race_date >= as_of_date)
    if not include_cancelled:
        statement = statement.where(Race.status == "active")
    return list(session.scalars(statement))


def get_race_usage(session: Session, *, race_id: int) -> RaceUsage:
    """Return reference counts before a mutable race action."""

    return RaceUsage(
        plan_count=session.scalar(
            select(func.count()).select_from(TrainingPlan).where(TrainingPlan.race_id == race_id)
        )
        or 0,
        accepted_plan_count=session.scalar(
            select(func.count())
            .select_from(TrainingPlan)
            .where(TrainingPlan.race_id == race_id, TrainingPlan.status == "accepted")
        )
        or 0,
        performance_evidence_count=session.scalar(
            select(func.count())
            .select_from(PerformanceEvidence)
            .where(PerformanceEvidence.race_id == race_id)
        )
        or 0,
    )


def delete_race(session: Session, *, race: Race) -> None:
    """Delete only after the caller checked all local references."""

    session.delete(race)
    session.flush()
