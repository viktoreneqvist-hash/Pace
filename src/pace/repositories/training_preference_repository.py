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
    available_days: list[dict[str, object]],
) -> TrainingPreference:
    preference = get_training_preference(session)
    if preference is None:
        preference = TrainingPreference(
            sport_role=sport_role,
            available_days=available_days,
        )
        session.add(preference)
    else:
        preference.sport_role = sport_role
        preference.available_days = available_days
    session.flush()
    return preference
