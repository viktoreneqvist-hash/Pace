from running_agent.integrations.garmin_mapper import (
    map_garmin_activity_to_activity,
)
from running_agent.repositories.activity_repository import save_activity
from running_agent.database import engine
from sqlalchemy.orm import Session


def import_activity(activity_data: dict):
    activity = map_garmin_activity_to_activity(activity_data)

    with Session(engine) as session:
        return save_activity(session, activity)