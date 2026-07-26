from datetime import UTC, date, datetime

from pace.database.models import Activity, ContextEvent, DailyMetric, SyncRun
from pace.database.session import session_scope
from pace.services.athlete_state_service import AthleteStateService


def test_athlete_state_combines_facts_relevant_context_and_data_quality():
    with session_scope() as session:
        session.add_all(
            [
                Activity(
                    provider="test",
                    provider_activity_id="run-1",
                    sport_type="run",
                    start_time=datetime(2026, 7, 25, 7, tzinfo=UTC),
                    distance_meters=10_000,
                    duration_seconds=3_600,
                    raw_payload={},
                ),
                DailyMetric(
                    date=date(2026, 7, 25),
                    hrv_value=55,
                    raw_payload={},
                ),
                ContextEvent(
                    event_type="travel",
                    start_date=date(2026, 7, 18),
                    end_date=date(2026, 7, 20),
                    note="Trip.",
                    affected_metrics=[],
                    status="closed",
                ),
                ContextEvent(
                    event_type="poor_sleep",
                    start_date=date(2026, 7, 18),
                    end_date=date(2026, 7, 18),
                    note="Outside the state window.",
                    affected_metrics=[],
                    status="closed",
                ),
                ContextEvent(
                    event_type="pain",
                    start_date=date(2026, 7, 17),
                    end_date=None,
                    note="Ongoing symptom.",
                    affected_metrics=[],
                    status="active",
                ),
                SyncRun(
                    provider="garmin",
                    completed_at=datetime(2026, 7, 25, 12, tzinfo=UTC),
                    status="partial",
                    requested_start_date=date(2026, 7, 19),
                    requested_end_date=date(2026, 7, 25),
                ),
            ]
        )

    athlete_state = AthleteStateService().get_state(end_date=date(2026, 7, 25))

    assert athlete_state.as_of_date == date(2026, 7, 25)
    assert athlete_state.metrics.training.current.running_distance_km == 10
    assert athlete_state.relevant_context.start_date == date(2026, 7, 19)
    assert [event.event_type for event in athlete_state.relevant_context.events] == [
        "pain",
        "travel",
    ]
    assert athlete_state.data_quality.latest_completed_sync is not None
    assert athlete_state.data_quality.latest_completed_sync.status == "partial"
    assert athlete_state.data_quality.latest_completed_sync.completed_at.tzinfo == UTC
    assert athlete_state.data_quality.recovery[0].metric == "hrv"
    assert athlete_state.data_quality.recovery[0].baseline_data_points == 1
    assert athlete_state.data_quality.recovery[0].expected_baseline_days == 28


def test_athlete_state_is_explicit_when_no_completed_sync_exists():
    athlete_state = AthleteStateService().get_state(end_date=date(2026, 7, 25))

    assert athlete_state.data_quality.latest_completed_sync is None
    assert all(
        metric.baseline_data_points == 0
        for metric in athlete_state.data_quality.recovery
    )


def test_athlete_state_marks_garmin_owned_values_as_current_or_stale_by_date():
    with session_scope() as session:
        session.add_all(
            [
                DailyMetric(
                    date=date(2026, 7, 24),
                    training_readiness=72,
                    recovery_time_hours=18,
                    raw_payload={},
                ),
                DailyMetric(
                    date=date(2026, 7, 25),
                    body_battery_high=81,
                    average_stress=32,
                    raw_payload={},
                ),
            ]
        )

    athlete_state = AthleteStateService().get_state(end_date=date(2026, 7, 25))
    facts = {fact.signal: fact for fact in athlete_state.garmin_current_facts}

    assert facts["training_readiness"].value == 72
    assert facts["training_readiness"].source_date == date(2026, 7, 24)
    assert facts["training_readiness"].is_current is False
    assert facts["body_battery_high"].value == 81
    assert facts["body_battery_high"].source_date == date(2026, 7, 25)
    assert facts["body_battery_high"].is_current is True
