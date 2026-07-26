"""Persistence for Pace's single athlete planning preference profile."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from pace.database.models import TrainingPreference


def get_training_preference(session: Session) -> TrainingPreference | None:
    return session.scalar(select(TrainingPreference).order_by(TrainingPreference.id).limit(1))


def upsert_training_preference(
    session: Session,
    *,
    sport_role: str,
    coaching_ambition: str,
    available_days: list[dict[str, object]],
) -> TrainingPreference:
    preference = get_training_preference(session)
    if preference is None:
        preference = TrainingPreference(
            sport_role=sport_role,
            coaching_ambition=coaching_ambition,
            available_days=available_days,
        )
        session.add(preference)
    else:
        preference.sport_role = sport_role
        preference.coaching_ambition = coaching_ambition
        preference.available_days = available_days
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
