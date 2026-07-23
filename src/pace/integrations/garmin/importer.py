from sqlalchemy.orm import Session

from pace.database import engine
from pace.integrations.garmin.normalizers import normalize_garmin_activity
from pace.repositories.activity_repository import save_activity


def import_activity(activity_data: dict):
    activity = normalize_garmin_activity(activity_data)

    with Session(engine) as session:
        return save_activity(session, activity)
