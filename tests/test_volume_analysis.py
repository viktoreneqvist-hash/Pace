from datetime import UTC, date, datetime

from pace.analysis.volume_analysis import (
    filter_activities_by_sport_type,
    get_distance_last_n_days,
    get_longest_activity,
    get_total_distance_km,
)
from pace.database.models import Activity


def activity(
    identifier: str,
    activity_date: date,
    sport_type: str,
    distance_km: float,
    duration_seconds: int,
) -> Activity:
    return Activity(
        provider="test",
        provider_activity_id=identifier,
        sport_type=sport_type,
        start_time=datetime.combine(activity_date, datetime.min.time(), tzinfo=UTC),
        distance_meters=distance_km * 1000,
        duration_seconds=duration_seconds,
        raw_payload={},
    )


def test_get_total_distance_km():
    activities = [
        activity("1", date(2026, 6, 1), "run", 10.0, 3000),
        activity("2", date(2026, 6, 2), "run", 5.5, 1800),
    ]

    assert get_total_distance_km(activities) == 15.5


def test_get_distance_last_n_days():
    activities = [
        activity("1", date(2026, 6, 1), "run", 10.0, 3000),
        activity("2", date(2026, 6, 8), "run", 7.0, 2400),
        activity("3", date(2026, 6, 10), "run", 5.0, 1800),
    ]

    assert get_distance_last_n_days(activities, end_date=date(2026, 6, 10), days=7) == 12.0


def test_get_longest_activity():
    activities = [
        activity("1", date(2026, 6, 1), "run", 10.0, 3000),
        activity("2", date(2026, 6, 2), "run", 21.1, 5400),
    ]

    longest = get_longest_activity(activities)

    assert longest is not None
    assert longest.distance_meters == 21_100


def test_get_longest_activity_empty_list():
    assert get_longest_activity([]) is None

def test_filter_activities_by_sport_type():
    activities = [
        activity("1", date(2026, 6, 1), "run", 10.0, 3000),
        activity("2", date(2026, 6, 2), "ride", 20.0, 3600),
        activity("3", date(2026, 6, 3), "run", 5.0, 1500),
    ]

    filtered = filter_activities_by_sport_type(activities, "run")

    assert len(filtered) == 2
    assert all(activity.sport_type == "run" for activity in filtered)
