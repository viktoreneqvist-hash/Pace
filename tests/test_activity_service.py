from datetime import date

from sqlalchemy import delete
from sqlalchemy.orm import Session

from pace.database import create_database_tables, engine
from pace.models.activity import Activity
from pace.services.activity_service import create_activity, get_all_activities


def clear_activities_table() -> None:
    with Session(engine) as session:
        session.execute(delete(Activity))
        session.commit()


def test_create_and_get_activity():
    create_database_tables()
    clear_activities_table()

    created_activity = create_activity(
        activity_date=date(2026, 6, 14),
        sport_type="running",
        distance_km=10.0,
        duration_s=3000,
        average_hr=150,
        max_hr=175,
        elevation_gain_m=120.0,
        source="manual",
        external_id="test-activity-1",
    )

    activities = get_all_activities()

    assert created_activity.id is not None
    assert len(activities) == 1
    assert activities[0].external_id == "test-activity-1"
