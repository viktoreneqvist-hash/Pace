from datetime import UTC, date, datetime
from types import SimpleNamespace

from pace.services.coach_training_history_service import (
    build_coach_training_history,
    build_planning_continuity_facts,
)
from pace.trends.models import FeedbackTrendRecord


def _activity(*, activity_date, sport_type, duration_seconds, distance_meters):
    return SimpleNamespace(
        start_time=datetime.combine(activity_date, datetime.min.time(), tzinfo=UTC),
        sport_type=sport_type,
        duration_seconds=duration_seconds,
        distance_meters=distance_meters,
        elevation_gain_meters=120.0,
        average_heart_rate=140,
        maximum_heart_rate=165,
        average_speed_mps=3.5,
        average_power=210.0,
        training_effect_aerobic=3.1,
        training_effect_anaerobic=0.4,
        provider_activity_id="must-not-reach-coach",
        name="must-not-reach-coach",
        raw_payload={"must-not-reach-coach": True},
    )


def test_history_uses_three_day_details_28_daily_rows_and_84_day_weeks():
    end_date = date(2026, 7, 27)
    history = build_coach_training_history(
        end_date=end_date,
        activities=(
            _activity(
                activity_date=date(2026, 7, 27),
                sport_type="ride",
                duration_seconds=3_000,
                distance_meters=20_000.0,
            ),
            _activity(
                activity_date=date(2026, 7, 25),
                sport_type="run",
                duration_seconds=1_800,
                distance_meters=None,
            ),
            _activity(
                activity_date=date(2026, 5, 11),
                sport_type="ride",
                duration_seconds=7_200,
                distance_meters=80_000.0,
            ),
        ),
        daily_metrics=(
            SimpleNamespace(
                date=end_date,
                hrv_value=91.0,
                resting_heart_rate=47,
                sleep_duration_seconds=28_800,
            ),
        ),
        feedback=(
            FeedbackTrendRecord(
                scheduled_date=end_date,
                sport_type="ride",
                outcome="completed",
                perceived_exertion=5,
                reason_code=None,
            ),
        ),
        context_events=(
            SimpleNamespace(
                event_type="travel",
                start_date=end_date,
                end_date=None,
                note="must-not-reach-coach",
            ),
        ),
    )

    assert len(history["recent_detailed_activities"]) == 2
    assert len(history["daily_history"]) == 28
    assert len(history["weekly_history"]) == 12
    assert history["recent_detailed_activities"][0]["sport_type"] == "run"
    assert "name" not in history["recent_detailed_activities"][0]
    assert "raw_payload" not in history["recent_detailed_activities"][0]
    today = history["daily_history"][-1]
    assert today["recovery"]["hrv_value"] == 91.0
    assert today["context_event_types"] == ["travel"]
    assert today["explicit_feedback"][0]["perceived_exertion"] == 5
    assert history["limits"]["historical_garmin_statuses_included"] is False


def test_daily_history_preserves_missing_distance_instead_of_converting_it_to_zero():
    history = build_coach_training_history(
        end_date=date(2026, 7, 27),
        activities=(
            _activity(
                activity_date=date(2026, 7, 27),
                sport_type="run",
                duration_seconds=1_800,
                distance_meters=None,
            ),
        ),
        daily_metrics=(),
        feedback=(),
        context_events=(),
    )

    run = history["daily_history"][-1]["training"]["run"]

    assert run["known_distance_meters"] == 0
    assert run["missing_distance_activity_count"] == 1


def test_planning_continuity_keeps_training_timeline_without_private_or_recovery_data():
    history = build_coach_training_history(
        end_date=date(2026, 7, 27),
        activities=(
            _activity(
                activity_date=date(2026, 7, 27),
                sport_type="ride",
                duration_seconds=3_000,
                distance_meters=20_000.0,
            ),
        ),
        daily_metrics=(
            SimpleNamespace(
                date=date(2026, 7, 27),
                hrv_value=91.0,
                resting_heart_rate=47,
                sleep_duration_seconds=28_800,
            ),
        ),
        feedback=(
            FeedbackTrendRecord(
                scheduled_date=date(2026, 7, 27),
                sport_type="ride",
                outcome="completed",
                perceived_exertion=5,
                reason_code=None,
            ),
        ),
        context_events=(
            SimpleNamespace(
                event_type="travel",
                start_date=date(2026, 7, 27),
                end_date=None,
                note="must-not-reach-plan",
            ),
        ),
    )

    continuity = build_planning_continuity_facts(history)

    assert len(continuity["daily_training"]) == 28
    assert len(continuity["weekly_training"]) == 12
    assert continuity["daily_training"][-1]["training"]["ride"]["activity_count"] == 1
    assert continuity["weekly_training"][-1]["active_days"] == 1
    latest_week = continuity["recent_windows"][0]
    assert latest_week["calendar_days"] == 7
    assert latest_week["training"]["ride"]["duration_seconds"] == 3_000
    assert latest_week["training"]["ride"]["active_days"] == 1
    assert "hrv_value" not in str(continuity)
    assert "must-not-reach-plan" not in str(continuity)
    assert "perceived_exertion" not in str(continuity)


def test_planning_continuity_separates_recent_drop_from_established_baseline():
    def week(*, start_date, end_date, activity_count, duration_seconds):
        return {
            "start_date": start_date,
            "end_date": end_date,
            "training": {
                "run": {
                    "activity_count": activity_count,
                    "duration_seconds": duration_seconds,
                    "known_distance_meters": 15_000,
                    "missing_distance_activity_count": 0,
                },
                "ride": {
                    "activity_count": 0,
                    "duration_seconds": 0,
                    "known_distance_meters": 0,
                    "missing_distance_activity_count": 0,
                },
            },
            "active_days": activity_count,
        }

    weekly_history = [
        week(
            start_date=f"2026-06-{day:02d}",
            end_date=f"2026-06-{day + 6:02d}",
            activity_count=3,
            duration_seconds=6_000,
        )
        for day in (1, 8, 15, 22)
    ] + [
        week(
            start_date="2026-07-01",
            end_date="2026-07-07",
            activity_count=3,
            duration_seconds=6_000,
        ),
        week(
            start_date="2026-07-08",
            end_date="2026-07-14",
            activity_count=3,
            duration_seconds=6_000,
        ),
        week(
            start_date="2026-07-15",
            end_date="2026-07-21",
            activity_count=1,
            duration_seconds=1_800,
        ),
        week(
            start_date="2026-07-22",
            end_date="2026-07-28",
            activity_count=1,
            duration_seconds=1_800,
        ),
    ]

    continuity = build_planning_continuity_facts(
        {
            "daily_history": [],
            "weekly_history": weekly_history,
            "limits": {"daily_history_days": 28, "weekly_history_days": 84},
        }
    )

    baseline = continuity["established_baseline"]
    run = baseline["sports"]["run"]
    assert baseline["excluded_most_recent_days"] == 14
    assert baseline["calendar_weeks"] == 6
    assert run["weeks_with_activity"] == 6
    assert run["activity_count_weekly_median"] == 3.0
    assert run["duration_seconds_weekly_median"] == 6_000.0
    assert continuity["weekly_training"][-1]["training"]["run"]["activity_count"] == 1
