from datetime import UTC, date, datetime

from pace.capacity.analysis import (
    summarize_continuity,
    summarize_sport_balance,
    summarize_sport_capacity,
)
from pace.capacity.models import SportCapacityFact
from pace.database.models import Activity


def _activity(
    identifier: str,
    activity_date: date,
    sport_type: str,
    distance_km: float | None,
    duration_seconds: int,
) -> Activity:
    return Activity(
        provider="test",
        provider_activity_id=identifier,
        sport_type=sport_type,
        start_time=datetime.combine(activity_date, datetime.min.time(), tzinfo=UTC),
        distance_meters=None if distance_km is None else distance_km * 1000,
        duration_seconds=duration_seconds,
        raw_payload={},
    )


def test_capacity_facts_keep_missing_distance_unknown_and_exclude_other_sports():
    activities = [
        _activity("run-known", date(2026, 7, 1), "run", 10, 3600),
        _activity("run-unknown", date(2026, 7, 8), "run", None, 1800),
        _activity("ride", date(2026, 7, 20), "ride", 45, 7200),
        _activity("other", date(2026, 7, 21), "other", 20, 7200),
    ]

    run = summarize_sport_capacity(
        activities,
        sport_type="run",
        start_date=date(2026, 6, 28),
        end_date=date(2026, 7, 25),
    )
    ride = summarize_sport_capacity(
        activities,
        sport_type="ride",
        start_date=date(2026, 6, 28),
        end_date=date(2026, 7, 25),
    )

    assert run.activity_count == 2
    assert run.total_duration_hours == 1.5
    assert run.total_distance_km is None
    assert run.longest_distance_km is None
    assert ride.activity_count == 1
    assert ride.total_distance_km == 45
    assert ride.longest_duration_hours == 2


def test_continuity_uses_fixed_seven_day_windows_and_calendar_inactive_streaks():
    activities = [
        _activity("run-1", date(2026, 7, 1), "run", 10, 3600),
        _activity("run-2", date(2026, 7, 8), "run", 5, 1800),
        _activity("ride", date(2026, 7, 20), "ride", 40, 7200),
    ]

    continuity = summarize_continuity(
        activities,
        start_date=date(2026, 6, 28),
        end_date=date(2026, 7, 25),
    )

    assert continuity.calendar_days == 28
    assert continuity.active_days == 3
    assert continuity.expected_weeks == 4
    assert continuity.weeks_with_activity == 3
    assert continuity.weeks_without_activity == 1
    assert continuity.longest_inactive_streak_days == 11


def test_sport_balance_uses_duration_not_incompatible_run_and_ride_distances():
    balance = summarize_sport_balance(
        (
            SportCapacityFact("run", 1, 1, 3, 30, 3, 30),
            SportCapacityFact("ride", 1, 1, 1, 25, 1, 25),
        )
    )

    assert balance.total_duration_hours == 4
    assert balance.running_duration_share_percent == 75
    assert balance.cycling_duration_share_percent == 25
