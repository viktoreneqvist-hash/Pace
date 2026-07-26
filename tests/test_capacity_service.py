from datetime import UTC, date, datetime

from pace.database.models import Activity, ContextEvent, SyncRun
from pace.database.session import session_scope
from pace.services.capacity_service import CapacityService


def _sync(start_date: date, end_date: date) -> SyncRun:
    return SyncRun(
        provider="garmin",
        completed_at=datetime(2026, 7, 26, 8, tzinfo=UTC),
        status="success",
        requested_start_date=start_date,
        requested_end_date=end_date,
    )


def _activity(
    identifier: str,
    activity_date: date,
    sport_type: str,
    distance_meters: float | None,
    duration_seconds: int,
) -> Activity:
    return Activity(
        provider="garmin",
        provider_activity_id=identifier,
        sport_type=sport_type,
        start_time=datetime.combine(activity_date, datetime.min.time(), tzinfo=UTC),
        distance_meters=distance_meters,
        duration_seconds=duration_seconds,
        raw_payload={"must_not_leave_capacity_profile": True},
    )


def _add_contiguous_history() -> None:
    with session_scope() as session:
        session.add_all(
            [
                _sync(date(2026, 6, 28), date(2026, 7, 4)),
                _sync(date(2026, 7, 5), date(2026, 7, 11)),
                _sync(date(2026, 7, 12), date(2026, 7, 18)),
                _sync(date(2026, 7, 19), date(2026, 7, 25)),
                _activity("run-1", date(2026, 7, 1), "run", 10_000, 3600),
                _activity("run-2", date(2026, 7, 8), "run", None, 1800),
                _activity("ride-1", date(2026, 7, 20), "ride", 45_000, 7200),
            ]
        )


def test_capacity_profile_reports_actual_training_and_j2c_target_limitations():
    _add_contiguous_history()

    profile = CapacityService().get_profile(end_date=date(2026, 7, 26))

    assert profile.status == "ready"
    assert profile.source_start_date == date(2026, 6, 28)
    assert profile.source_end_date == date(2026, 7, 25)
    assert profile.continuity is not None
    assert profile.continuity.weeks_without_activity == 1
    run, ride = profile.sports
    assert run.total_distance_km is None
    assert ride.total_distance_km == 45
    assert profile.sport_balance is not None
    assert profile.sport_balance.running_duration_share_percent == 42.857142857142854
    assert profile.planning_blockers == ()
    assert "performance_targets_pending_j2c" in profile.limitations


def test_capacity_profile_remains_visible_but_is_blocked_for_active_illness():
    _add_contiguous_history()
    with session_scope() as session:
        session.add(
            ContextEvent(
                event_type="illness",
                start_date=date(2026, 7, 20),
                end_date=None,
                note="Private illness note.",
                affected_metrics=[],
                status="active",
            )
        )

    profile = CapacityService().get_profile(end_date=date(2026, 7, 26))

    assert profile.status == "blocked"
    assert profile.sports[0].activity_count == 2
    assert profile.planning_blockers[0].code == "active_illness"
    assert not hasattr(profile.planning_blockers[0], "note")
