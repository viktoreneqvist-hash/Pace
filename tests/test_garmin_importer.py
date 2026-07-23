from sqlalchemy import delete
from sqlalchemy.orm import Session

from pace.database import create_database_tables, engine
from pace.integrations.garmin.importer import import_activity
from pace.models.activity import Activity
from pace.services.activity_service import get_all_activities


def clear_activities_table() -> None:
    with Session(engine) as session:
        session.execute(delete(Activity))
        session.commit()


def test_import_activity_from_mock_json():
    create_database_tables()
    clear_activities_table()

    mock_activity = {
        "date": "2026-06-14",
        "sport_type": "running",
        "distance_m": 10000,
        "duration_s": 3000,
        "average_hr": 150,
        "max_hr": 175,
        "elevation_gain_m": 120.0,
        "external_id": "mock-garmin-1",
    }

    imported_activity = import_activity(mock_activity)
    activities = get_all_activities()

    assert imported_activity.id is not None
    assert len(activities) == 1
    assert activities[0].external_id == "mock-garmin-1"
    assert activities[0].distance_km == 10.0
