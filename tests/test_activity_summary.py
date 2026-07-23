from datetime import date

from pace.analysis.activity_summary import calculate_total_distance_km
from pace.models.activity import Activity


def test_calculate_total_distance_km():
    activities = [
        Activity(
            date=date(2026, 6, 14),
            sport_type="running",
            distance_km=10.0,
            duration_s=3000,
            source="manual",
        ),
        Activity(
            date=date(2026, 6, 15),
            sport_type="running",
            distance_km=5.5,
            duration_s=1600,
            source="manual",
        ),
    ]

    total_distance = calculate_total_distance_km(activities)

    assert total_distance == 15.5
