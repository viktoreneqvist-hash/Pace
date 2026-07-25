from datetime import datetime
from uuid import uuid4

from pace.database.models import Activity
from pace.database.session import session_scope
from pace.repositories.activity_repository import get_all_activities as repository_get_all_activities
from pace.repositories.activity_repository import upsert_activity


def create_activity(
    start_time: datetime,
    sport_type: str,
    distance_meters: float | None,
    duration_seconds: int,
    average_heart_rate: int | None = None,
    maximum_heart_rate: int | None = None,
    elevation_gain_meters: float | None = None,
    provider: str = "manual",
    provider_activity_id: str | None = None,
) -> Activity:
    """Create or update a manually entered activity."""

    activity = Activity(
        provider=provider,
        provider_activity_id=provider_activity_id or f"manual-{uuid4()}",
        sport_type=sport_type,
        start_time=start_time,
        distance_meters=distance_meters,
        duration_seconds=duration_seconds,
        average_heart_rate=average_heart_rate,
        maximum_heart_rate=maximum_heart_rate,
        elevation_gain_meters=elevation_gain_meters,
        raw_payload={},
    )

    with session_scope() as session:
        saved_activity, _ = upsert_activity(session, activity)
        return saved_activity


def get_all_activities() -> list[Activity]:
    """Return every stored activity in chronological order."""

    with session_scope() as session:
        return repository_get_all_activities(session)
