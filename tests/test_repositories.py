from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from pace.database.models import Activity, ContextEvent, DailyMetric
from pace.database.session import SessionFactory, session_scope
from pace.repositories.activity_repository import (
    get_activities_in_date_range,
    upsert_activity,
)
from pace.repositories.context_event_repository import (
    create_context_event,
    get_context_events_for_date,
)
from pace.repositories.daily_metric_repository import upsert_daily_metric
from pace.repositories.sync_run_repository import complete_sync_run, create_sync_run


def test_activity_upsert_updates_an_existing_provider_record():
    first_activity = Activity(
        provider="garmin",
        provider_activity_id="123",
        sport_type="run",
        start_time=datetime(2026, 6, 14, tzinfo=UTC),
        duration_seconds=3000,
        distance_meters=10_000,
        raw_payload={"version": 1},
    )
    updated_activity = Activity(
        provider="garmin",
        provider_activity_id="123",
        sport_type="run",
        start_time=datetime(2026, 6, 14, tzinfo=UTC),
        duration_seconds=3010,
        distance_meters=10_100,
        raw_payload={"version": 2},
    )

    with session_scope() as session:
        stored_activity, created, changed = upsert_activity(session, first_activity)
        stored_id = stored_activity.id
        updated_record, created_again, changed_again = upsert_activity(
            session,
            updated_activity,
        )

        assert created is True
        assert changed is False
        assert created_again is False
        assert changed_again is True
        assert updated_record.id == stored_id
        assert updated_record.distance_meters == 10_100
        assert updated_record.raw_payload == {"version": 2}


def test_database_constraint_rejects_duplicate_provider_activity_ids():
    duplicate_activity = Activity(
        provider="garmin",
        provider_activity_id="123",
        sport_type="run",
        start_time=datetime(2026, 6, 14, tzinfo=UTC),
        duration_seconds=3000,
        raw_payload={},
    )

    with SessionFactory() as session:
        session.add_all(
            [
                duplicate_activity,
                Activity(
                    provider="garmin",
                    provider_activity_id="123",
                    sport_type="run",
                    start_time=datetime(2026, 6, 15, tzinfo=UTC),
                    duration_seconds=2800,
                    raw_payload={},
                ),
            ]
        )

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()


def test_activity_date_query_uses_stockholm_day_boundaries():
    with session_scope() as session:
        session.add_all(
            [
                Activity(
                    provider="garmin",
                    provider_activity_id="local-july-25",
                    sport_type="run",
                    start_time=datetime(2026, 7, 24, 22, 30, tzinfo=UTC),
                    duration_seconds=1800,
                    raw_payload={},
                ),
                Activity(
                    provider="garmin",
                    provider_activity_id="local-july-26",
                    sport_type="run",
                    start_time=datetime(2026, 7, 25, 22, 30, tzinfo=UTC),
                    duration_seconds=1800,
                    raw_payload={},
                ),
            ]
        )

    with session_scope() as session:
        activities = get_activities_in_date_range(
            session,
            start_date=date(2026, 7, 25),
            end_date=date(2026, 7, 25),
        )

    assert [activity.provider_activity_id for activity in activities] == [
        "local-july-25"
    ]


def test_daily_metric_upsert_updates_one_record_per_day():
    with session_scope() as session:
        _, created, changed = upsert_daily_metric(
            session,
            DailyMetric(
                date=date(2026, 6, 14),
                hrv_value=58.0,
                raw_payload={"source": "first"},
            ),
        )
        daily_metric, created_again, changed_again = upsert_daily_metric(
            session,
            DailyMetric(
                date=date(2026, 6, 14),
                hrv_value=60.0,
                raw_payload={"source": "second"},
            ),
        )

        assert created is True
        assert changed is False
        assert created_again is False
        assert changed_again is True
        assert daily_metric.hrv_value == 60.0
        assert daily_metric.raw_payload == {"source": "second"}


def test_context_events_can_be_queried_by_date_overlap():
    with session_scope() as session:
        create_context_event(
            session,
            ContextEvent(
                event_type="work_stress",
                start_date=date(2026, 6, 14),
                end_date=date(2026, 6, 16),
                note="Demanding work period.",
                affected_metrics=["sleep", "hrv"],
            ),
        )

        events = get_context_events_for_date(session, date(2026, 6, 15))

    assert len(events) == 1
    assert events[0].event_type == "work_stress"


def test_sync_run_records_a_partial_result():
    with session_scope() as session:
        sync_run = create_sync_run(
            session,
            provider="garmin",
            requested_start_date=date(2026, 6, 1),
            requested_end_date=date(2026, 6, 14),
        )

        completed_run = complete_sync_run(
            sync_run,
            status="partial",
            activities_fetched=3,
            activities_inserted=2,
            activities_updated=1,
            error_summary="Sleep endpoint was unavailable.",
        )

        assert completed_run.status == "partial"
        assert completed_run.completed_at is not None
        assert completed_run.activities_inserted == 2
        assert completed_run.error_summary == "Sleep endpoint was unavailable."
