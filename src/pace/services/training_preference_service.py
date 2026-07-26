"""Validate athlete-controlled feasibility preferences without performance claims."""

from dataclasses import dataclass

from pace.database.models import TrainingPreference
from pace.database.session import session_scope
from pace.repositories.training_preference_repository import (
    get_training_preference,
    upsert_training_preference,
    update_training_preference_ambition,
)


SUPPORTED_SPORT_ROLES = frozenset({"run_primary", "ride_primary", "balanced"})
SUPPORTED_COACHING_AMBITIONS = frozenset({"cautious", "balanced", "ambitious"})
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass(frozen=True, slots=True)
class TrainingPreferenceInput:
    sport_role: str
    available_days: tuple[str, ...]
    coaching_ambition: str | None = None


class TrainingPreferenceService:
    """Store availability and desired sport role separately from training capacity."""

    def set_preference(self, preference_input: TrainingPreferenceInput) -> TrainingPreference:
        sport_role = preference_input.sport_role.strip().lower()
        if sport_role not in SUPPORTED_SPORT_ROLES:
            raise ValueError(f"Unsupported sport role: {sport_role}.")
        available_days = _parse_available_days(preference_input.available_days)
        with session_scope() as session:
            existing = get_training_preference(session)
            coaching_ambition = _resolve_coaching_ambition(
                value=preference_input.coaching_ambition,
                existing=existing,
            )
            return upsert_training_preference(
                session,
                sport_role=sport_role,
                coaching_ambition=coaching_ambition,
                available_days=available_days,
            )

    def get_preference(self) -> TrainingPreference | None:
        with session_scope() as session:
            return get_training_preference(session)

    def set_coaching_ambition(self, *, coaching_ambition: str) -> TrainingPreference:
        """Change the athlete's stated ambition without resetting availability."""

        ambition = _resolve_coaching_ambition(value=coaching_ambition, existing=None)
        with session_scope() as session:
            preference = update_training_preference_ambition(
                session, coaching_ambition=ambition
            )
            if preference is None:
                raise ValueError("Set training preferences before setting coaching ambition.")
            return preference


def _parse_available_days(values: tuple[str, ...]) -> list[dict[str, object]]:
    parsed: list[dict[str, object]] = []
    seen_days: set[str] = set()
    if not values:
        raise ValueError("Choose at least one available day, for example --day mon:60.")
    for value in values:
        weekday, separator, minutes_text = value.strip().lower().partition(":")
        if not separator or weekday not in WEEKDAYS:
            raise ValueError("Each --day must have format mon:60 through sun:60.")
        if minutes_text == "any":
            minutes = None
        else:
            try:
                minutes = int(minutes_text)
            except ValueError as error:
                raise ValueError("Available day minutes must be a whole number or 'any'.") from error
            if minutes <= 0:
                raise ValueError("Available day minutes must be greater than zero.")
        if weekday in seen_days:
            raise ValueError(f"Availability has duplicate day: {weekday}.")
        seen_days.add(weekday)
        parsed.append({"day": weekday, "minutes": minutes})
    return parsed


def _resolve_coaching_ambition(
    *, value: str | None, existing: TrainingPreference | None
) -> str:
    if value is None:
        return "balanced" if existing is None else existing.coaching_ambition
    ambition = value.strip().lower()
    if ambition not in SUPPORTED_COACHING_AMBITIONS:
        raise ValueError(f"Unsupported coaching ambition: {ambition}.")
    return ambition
