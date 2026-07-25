from datetime import UTC, datetime

from pace.services.activity_service import create_activity, get_all_activities


def test_create_and_get_activity():
    created_activity = create_activity(
        start_time=datetime(2026, 6, 14, 9, tzinfo=UTC),
        sport_type="run",
        distance_meters=10_000,
        duration_seconds=3000,
        average_heart_rate=150,
        maximum_heart_rate=175,
        elevation_gain_meters=120.0,
        provider_activity_id="test-activity-1",
    )

    activities = get_all_activities()

    assert created_activity.id is not None
    assert len(activities) == 1
    assert activities[0].provider_activity_id == "test-activity-1"
