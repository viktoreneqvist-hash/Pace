"""Persistence for Pace's single athlete planning preference profile."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from pace.database.models import TrainingPreference


def get_training_preference(session: Session) -> TrainingPreference | None:
    return session.scalar(
        select(TrainingPreference).order_by(TrainingPreference.id).limit(1)
    )


def upsert_training_preference(
    session: Session,
    *,
    sport_role: str,
    coaching_ambition: str,
    available_days: list[dict[str, object]],
    base_running_distance_ceiling_km: float | None,
    base_cycling_duration_ceiling_hours: float | None,
    base_total_duration_ceiling_hours: float | None,
) -> TrainingPreference:
    preference = get_training_preference(session)
    if preference is None:
        preference = TrainingPreference(
            sport_role=sport_role,
            coaching_ambition=coaching_ambition,
            available_days=available_days,
            base_running_distance_ceiling_km=base_running_distance_ceiling_km,
            base_cycling_duration_ceiling_hours=base_cycling_duration_ceiling_hours,
            base_total_duration_ceiling_hours=base_total_duration_ceiling_hours,
        )
        session.add(preference)
    else:
        preference.sport_role = sport_role
        preference.coaching_ambition = coaching_ambition
        preference.available_days = available_days
        preference.base_running_distance_ceiling_km = base_running_distance_ceiling_km
        preference.base_cycling_duration_ceiling_hours = (
            base_cycling_duration_ceiling_hours
        )
        preference.base_total_duration_ceiling_hours = base_total_duration_ceiling_hours
    session.flush()
    return preference


def update_training_preference_ambition(
    session: Session,
    *,
    coaching_ambition: str,
) -> TrainingPreference | None:
    """Update only athlete intent, preserving sport role and availability."""

    preference = get_training_preference(session)
    if preference is None:
        return None
    preference.coaching_ambition = coaching_ambition
    session.flush()
    return preference
