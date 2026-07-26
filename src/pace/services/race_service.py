"""Validate and persist athlete-confirmed race goals without plan generation."""

from dataclasses import dataclass
from datetime import date

from pace.database.models import Race
from pace.database.session import session_scope
from pace.repositories.race_repository import (
    create_race,
    get_race_by_id,
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

    def update_race(
        self,
        *,
        race_id: int,
        priority: str | None = None,
        taper_override: str | None = None,
    ) -> Race:
        """Update only a race's priority or its explicit taper override."""

        if priority is None and taper_override is None:
            raise ValueError("Choose a priority or taper override to update.")

        with session_scope() as session:
            race = get_race_by_id(session, race_id)
            if race is None:
                raise ValueError(f"No race exists with id {race_id}.")
            if priority is not None:
                race.priority = _normalize_priority(priority)
            if taper_override is not None:
                race.taper_override = _normalize_taper_override(taper_override)
            session.flush()
            return race


def resolved_taper(race: Race) -> str:
    """Return the explicit override or the agreed A/B/C default policy."""

    return race.taper_override or DEFAULT_TAPER_BY_PRIORITY[race.priority]


def _validate_race_input(race_input: RaceInput) -> dict[str, object]:
    name = race_input.name.strip()
    if not name:
        raise ValueError("A race name cannot be empty.")
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
    }


def _normalize_sport_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in SUPPORTED_RACE_SPORT_TYPES:
        raise ValueError(f"Unsupported race sport type: {normalized}.")
    return normalized


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
