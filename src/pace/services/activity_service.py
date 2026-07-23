from datetime import date

from sqlalchemy.orm import Session

from pace.database import engine
from pace.models.activity import Activity
from pace.repositories.activity_repository import get_all_activities as repository_get_all_activities
from pace.repositories.activity_repository import save_activity


def create_activity(
    activity_date: date,
    sport_type: str,
    distance_km: float,
    duration_s: int,
    average_hr: int | None = None,
    max_hr: int | None = None,
    elevation_gain_m: float | None = None,
    source: str = "manual",
    external_id: str | None = None,
) -> Activity:
    activity = Activity(
        date=activity_date,
        sport_type=sport_type,
        distance_km=distance_km,
        duration_s=duration_s,
        average_hr=average_hr,
        max_hr=max_hr,
        elevation_gain_m=elevation_gain_m,
        source=source,
        external_id=external_id,
    )

    with Session(engine) as session:
        return save_activity(session, activity)


def get_all_activities() -> list[Activity]:
    with Session(engine) as session:
        return repository_get_all_activities(session)
