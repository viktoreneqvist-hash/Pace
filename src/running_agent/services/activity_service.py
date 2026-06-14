from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from running_agent.database import engine
from running_agent.models.activity import Activity


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
        session.add(activity)
        session.commit()
        session.refresh(activity)

        return activity


def get_all_activities() -> list[Activity]:
    with Session(engine) as session:
        statement = select(Activity)
        activities = session.scalars(statement).all()

        return list(activities)