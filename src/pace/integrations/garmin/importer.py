from pace.database.session import session_scope
from pace.integrations.garmin.normalizers import normalize_garmin_activity
from pace.repositories.activity_repository import upsert_activity


def import_activity(activity_data: dict):
    """Store a Garmin activity and return the normalized record."""

    activity = normalize_garmin_activity(activity_data)

    with session_scope() as session:
        saved_activity, _ = upsert_activity(session, activity)
        return saved_activity
