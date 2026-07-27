"""Validate and persist athlete-confirmed race goals without plan generation."""

from dataclasses import dataclass
from datetime import date

from pace.database.models import Race
from pace.database.session import session_scope
from pace.repositories.race_repository import (
    create_race,
    delete_race,
    get_race_by_id,
    get_race_usage,
    get_races,
    get_upcoming_races,
)


SUPPORTED_RACE_SPORT_TYPES = frozenset({"run", "ride"})
SUPPORTED_RACE_PRIORITIES = frozenset({"A", "B", "C"})
SUPPORTED_TAPER_OVERRIDES = frozenset({"full", "partial", "none"})
SUPPORTED_TAPER_CHOICES = frozenset({*SUPPORTED_TAPER_OVERRIDES, "default"})
DEFAULT_TAPER_BY_PRIORITY = {"A": "full", "B": "partial", "C": "none"}


@dataclass(frozen=True, slots=True)
class RaceInput:
    """Explicit athlete decisions required to define one upcoming race."""

    name: str
    sport_type: str
    race_date: date
    distance_meters: float
    priority: str
    desired_time_seconds: int | None = None
    taper_override: str | None = None


class RaceService:
    """Keep race goals structured, local, and separate from Garmin facts."""

    def add_race(self, race_input: RaceInput) -> Race:
        """Store one validated race objective without assessing its realism."""

        normalized = _validate_race_input(race_input)
        with session_scope() as session:
            return create_race(session, Race(**normalized))

    def list_upcoming_races(self, *, as_of_date: date) -> list[Race]:
        """List future race objectives for one reproducible planning date."""

        with session_scope() as session:
            return get_upcoming_races(session, as_of_date=as_of_date)

    def list_races(
        self,
        *,
        as_of_date: date,
        include_past: bool,
        include_cancelled: bool = False,
    ) -> list[Race]:
        """List race ids needed when explicitly linking a completed race result."""

        with session_scope() as session:
            return get_races(
                session,
                as_of_date=as_of_date,
                include_past=include_past,
                include_cancelled=include_cancelled,
            )

    def update_race(
        self,
        *,
        race_id: int,
        name: str | None = None,
        sport_type: str | None = None,
        race_date: date | None = None,
        distance_meters: float | None = None,
        desired_time_seconds: int | None = None,
        clear_desired_time: bool = False,
        priority: str | None = None,
        taper_override: str | None = None,
    ) -> Race:
        """Correct an unused race or adjust its current planning choices."""

        if all(
            value is None
            for value in (
                name,
                sport_type,
                race_date,
                distance_meters,
                desired_time_seconds,
                priority,
                taper_override,
            )
        ) and not clear_desired_time:
            raise ValueError("Choose at least one race field to update.")
        if desired_time_seconds is not None and clear_desired_time:
            raise ValueError("Choose desired time or --clear-desired-time, not both.")

        with session_scope() as session:
            race = get_race_by_id(session, race_id)
            if race is None:
                raise ValueError(f"No race exists with id {race_id}.")
            if race.status != "active":
                raise ValueError("A cancelled race cannot be updated.")
            fact_change_requested = any(
                value is not None
                for value in (name, sport_type, race_date, distance_meters, desired_time_seconds)
            ) or clear_desired_time
            if fact_change_requested and _has_references(get_race_usage(session, race_id=race_id)):
                raise ValueError(
                    "Race facts cannot change after a plan or Garmin result references it. "
                    "Create a new race instead."
                )
            if name is not None:
                race.name = _normalize_name(name)
            if sport_type is not None:
                race.sport_type = _normalize_sport_type(sport_type)
            if race_date is not None:
                race.race_date = race_date
            if distance_meters is not None:
                if distance_meters <= 0:
                    raise ValueError("Race distance must be greater than zero.")
                race.distance_meters = distance_meters
            if desired_time_seconds is not None:
                if desired_time_seconds <= 0:
                    raise ValueError("Desired race time must be greater than zero.")
                race.desired_time_seconds = desired_time_seconds
            if clear_desired_time:
                race.desired_time_seconds = None
            if priority is not None:
                race.priority = _normalize_priority(priority)
            if taper_override is not None:
                race.taper_override = _normalize_taper_override(taper_override)
            session.flush()
            return race

    def remove_race(self, *, race_id: int, as_of_date: date) -> None:
        """Remove only an unused future race; protect all linked history."""

        with session_scope() as session:
            race = get_race_by_id(session, race_id)
            if race is None:
                raise ValueError(f"No race exists with id {race_id}.")
            if race.race_date < as_of_date:
                raise ValueError("Past races are preserved as local history and cannot be removed.")
            if _has_references(get_race_usage(session, race_id=race_id)):
                raise ValueError(
                    "A race referenced by a plan or Garmin result cannot be removed. "
                    "Use race cancel when it is not an active accepted-plan target."
                )
            delete_race(session, race=race)

    def cancel_race(self, *, race_id: int, as_of_date: date) -> Race:
        """Hide an unused or draft-only future race without deleting history."""

        with session_scope() as session:
            race = get_race_by_id(session, race_id)
            if race is None:
                raise ValueError(f"No race exists with id {race_id}.")
            if race.status != "active":
                raise ValueError("Race is already cancelled.")
            if race.race_date < as_of_date:
                raise ValueError("Past races are preserved as local history and cannot be cancelled.")
            usage = get_race_usage(session, race_id=race_id)
            if usage.accepted_plan_count or usage.performance_evidence_count:
                raise ValueError(
                    "A race used by an accepted plan or Garmin result cannot be cancelled. "
                    "Create a new plan or preserve the historical race."
                )
            race.status = "cancelled"
            session.flush()
            return race


def resolved_taper(race: Race) -> str:
    """Return the explicit override or the agreed A/B/C default policy."""

    return race.taper_override or DEFAULT_TAPER_BY_PRIORITY[race.priority]


def _validate_race_input(race_input: RaceInput) -> dict[str, object]:
    name = _normalize_name(race_input.name)
    if race_input.distance_meters <= 0:
        raise ValueError("Race distance must be greater than zero.")
    if race_input.desired_time_seconds is not None and race_input.desired_time_seconds <= 0:
        raise ValueError("Desired race time must be greater than zero.")

    return {
        "name": name,
        "sport_type": _normalize_sport_type(race_input.sport_type),
        "race_date": race_input.race_date,
        "distance_meters": race_input.distance_meters,
        "priority": _normalize_priority(race_input.priority),
        "desired_time_seconds": race_input.desired_time_seconds,
        "taper_override": (
            None
            if race_input.taper_override is None
            else _normalize_taper_override(race_input.taper_override)
        ),
        "status": "active",
    }


def _normalize_sport_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in SUPPORTED_RACE_SPORT_TYPES:
        raise ValueError(f"Unsupported race sport type: {normalized}.")
    return normalized


def _normalize_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise ValueError("A race name cannot be empty.")
    return name


def _has_references(usage) -> bool:
    return bool(usage.plan_count or usage.performance_evidence_count)


def _normalize_priority(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in SUPPORTED_RACE_PRIORITIES:
        raise ValueError(f"Unsupported race priority: {normalized}.")
    return normalized


def _normalize_taper_override(value: str) -> str | None:
    normalized = value.strip().lower()
    if normalized == "default":
        return None
    if normalized not in SUPPORTED_TAPER_OVERRIDES:
        raise ValueError(f"Unsupported taper override: {normalized}.")
    return normalized
