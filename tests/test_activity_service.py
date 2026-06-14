from datetime import date

from running_agent.database import create_database_tables
from running_agent.services.activity_service import create_activity, get_all_activities


def test_create_and_get_activity():
    create_database_tables()

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
    assert any(activity.external_id == "test-activity-1" for activity in activities)