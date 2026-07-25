from datetime import UTC, datetime

from pace.analysis.activity_summary import calculate_total_distance_km
from pace.database.models import Activity


def test_calculate_total_distance_km():
    activities = [
        Activity(
            provider="test",
            provider_activity_id="activity-1",
            sport_type="running",
            start_time=datetime(2026, 6, 14, tzinfo=UTC),
            distance_meters=10_000,
            duration_seconds=3000,
            raw_payload={},
        ),
        Activity(
            provider="test",
            provider_activity_id="activity-2",
            sport_type="running",
            start_time=datetime(2026, 6, 15, tzinfo=UTC),
            distance_meters=5_500,
            duration_seconds=1600,
            raw_payload={},
        ),
    ]

    total_distance = calculate_total_distance_km(activities)

    assert total_distance == 15.5
