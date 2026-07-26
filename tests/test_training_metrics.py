from datetime import UTC, date, datetime

from pace.analysis.training_metrics import summarize_weekly_training
from pace.database.models import Activity


def activity(
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
        distance_meters=distance_km * 1000 if distance_km is not None else None,
        duration_seconds=duration_seconds,
        raw_payload={},
    )


def test_weekly_training_summary_compares_two_explicit_seven_day_windows():
    summary = summarize_weekly_training(
        [
            activity("previous-run", date(2026, 6, 2), "run", 10, 3600),
            activity("previous-ride", date(2026, 6, 5), "ride", 30, 7200),
            activity("current-run-1", date(2026, 6, 8), "run", 8, 3000),
            activity("current-run-2", date(2026, 6, 10), "run", 12, 4200),
            activity("current-ride", date(2026, 6, 14), "ride", 40, 10800),
            activity("ignored-strength", date(2026, 6, 12), "other", None, 7200),
        ],
        end_date=date(2026, 6, 14),
    )

    assert summary.current.start_date == date(2026, 6, 8)
    assert summary.current.activity_count == 3
    assert summary.current.active_days == 3
    assert summary.current.running_distance_km == 20
    assert summary.current.cycling_duration_hours == 3
    assert summary.current.total_duration_hours == 5
    assert summary.current.longest_run_km == 12
    assert summary.current.longest_ride_km == 40
    assert summary.previous.running_distance_km == 10
    assert summary.previous.cycling_duration_hours == 2
    assert summary.running_distance_change_percent == 100
    assert summary.cycling_duration_change_percent == 50


def test_progression_is_not_invented_when_previous_window_is_zero():
    summary = summarize_weekly_training(
        [activity("current-run", date(2026, 6, 14), "run", 5, 1800)],
        end_date=date(2026, 6, 14),
    )

    assert summary.running_distance_change_percent is None
    assert summary.cycling_duration_change_percent is None


def test_missing_run_distance_keeps_distance_facts_unknown():
    summary = summarize_weekly_training(
        [
            activity("known-run", date(2026, 6, 13), "run", 5, 1800),
            activity("unknown-run", date(2026, 6, 14), "run", None, 1200),
        ],
        end_date=date(2026, 6, 14),
    )

    assert summary.current.activity_count == 2
    assert summary.current.running_distance_km is None
    assert summary.current.longest_run_km is None
    assert summary.running_distance_change_percent is None


def test_training_windows_use_the_stockholm_calendar_date():
    summary = summarize_weekly_training(
        [
            Activity(
                provider="test",
                provider_activity_id="late-stockholm-run",
                sport_type="run",
                start_time=datetime(2026, 7, 24, 22, 30, tzinfo=UTC),
                distance_meters=5_000,
                duration_seconds=1800,
                raw_payload={},
            ),
            Activity(
                provider="test",
                provider_activity_id="next-stockholm-day",
                sport_type="run",
                start_time=datetime(2026, 7, 25, 22, 30, tzinfo=UTC),
                distance_meters=6_000,
                duration_seconds=2000,
                raw_payload={},
            ),
        ],
        end_date=date(2026, 7, 25),
    )

    assert summary.current.activity_count == 1
    assert summary.current.running_distance_km == 5
    assert summary.current.active_days == 1
