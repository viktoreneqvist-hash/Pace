from datetime import date

from running_agent.analysis.volume_analysis import (
    filter_activities_by_sport_type,
    get_distance_last_n_days,
    get_longest_activity,
    get_total_distance_km,
)
from running_agent.models.activity import Activity


def test_get_total_distance_km():
    activities = [
        Activity(date=date(2026, 6, 1), sport_type="Run", distance_km=10.0, duration_s=3000, source="test"),
        Activity(date=date(2026, 6, 2), sport_type="Run", distance_km=5.5, duration_s=1800, source="test"),
    ]

    assert get_total_distance_km(activities) == 15.5


def test_get_distance_last_n_days():
    activities = [
        Activity(date=date(2026, 6, 1), sport_type="Run", distance_km=10.0, duration_s=3000, source="test"),
        Activity(date=date(2026, 6, 8), sport_type="Run", distance_km=7.0, duration_s=2400, source="test"),
        Activity(date=date(2026, 6, 10), sport_type="Run", distance_km=5.0, duration_s=1800, source="test"),
    ]

    assert get_distance_last_n_days(activities, end_date=date(2026, 6, 10), days=7) == 12.0


def test_get_longest_activity():
    activities = [
        Activity(date=date(2026, 6, 1), sport_type="Run", distance_km=10.0, duration_s=3000, source="test"),
        Activity(date=date(2026, 6, 2), sport_type="Run", distance_km=21.1, duration_s=5400, source="test"),
    ]

    longest = get_longest_activity(activities)

    assert longest is not None
    assert longest.distance_km == 21.1


def test_get_longest_activity_empty_list():
    assert get_longest_activity([]) is None

def test_filter_activities_by_sport_type():
    activities = [
        Activity(date=date(2026, 6, 1), sport_type="Run", distance_km=10.0, duration_s=3000, source="test"),
        Activity(date=date(2026, 6, 2), sport_type="Bike", distance_km=20.0, duration_s=3600, source="test"),
        Activity(date=date(2026, 6, 3), sport_type="Run", distance_km=5.0, duration_s=1500, source="test"),
    ]

    filtered = filter_activities_by_sport_type(activities, "Run")

    assert len(filtered) == 2
    assert all(activity.sport_type == "Run" for activity in filtered)

    