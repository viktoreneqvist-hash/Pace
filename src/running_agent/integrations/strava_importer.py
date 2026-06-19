from sqlalchemy.orm import Session

from running_agent.database import engine
from running_agent.integrations.strava_client import get_athlete_activities
from running_agent.integrations.strava_mapper import map_strava_activity_to_activity
from running_agent.repositories.activity_repository import (
    get_activity_by_external_id,
    save_activity,
)


def import_recent_strava_activities(per_page: int = 50) -> list[dict]:
    strava_activities = get_athlete_activities(per_page=per_page)
    imported_activities = []

    with Session(engine) as session:
        for strava_activity in strava_activities:
            external_id = str(strava_activity["id"])

            existing_activity = get_activity_by_external_id(session, external_id)
            if existing_activity is not None:
                continue

            activity = map_strava_activity_to_activity(strava_activity)
            imported_activity = save_activity(session, activity)

            imported_activities.append(
                {
                    "id": imported_activity.id,
                    "date": imported_activity.date,
                    "sport_type": imported_activity.sport_type,
                    "distance_km": imported_activity.distance_km,
                    "source": imported_activity.source,
                    "external_id": imported_activity.external_id,
                }
            )

    return imported_activities