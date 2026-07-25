from datetime import UTC, date, datetime

from pace.database.models import Activity, DailyMetric
from pace.database.session import session_scope
from pace.services.metric_service import MetricService


def test_metric_service_reads_local_database_and_returns_structured_facts():
    with session_scope() as session:
        session.add_all(
            [
                Activity(
                    provider="test",
                    provider_activity_id="run-1",
                    sport_type="run",
                    start_time=datetime(2026, 6, 14, tzinfo=UTC),
                    distance_meters=10_000,
                    duration_seconds=3600,
                    raw_payload={},
                ),
                DailyMetric(
                    date=date(2026, 6, 14),
                    hrv_value=55,
                    resting_heart_rate=47,
                    sleep_duration_seconds=28_800,
                    raw_payload={},
                ),
            ]
        )

    summary = MetricService().get_summary(end_date=date(2026, 6, 14))

    assert summary.training.current.running_distance_km == 10
    assert summary.training.current.activity_count == 1
    assert summary.recovery[0].metric == "hrv"
    assert summary.recovery[0].latest_value == 55
