import json
from datetime import date
from pathlib import Path

from sqlalchemy import select

from pace.database.models import Activity, DailyMetric, SyncRun
from pace.database.session import SessionFactory
from pace.integrations.garmin.client import GarminIntegrationError
from pace.services.garmin_sync_service import GarminSyncService


FIXTURES_PATH = Path(__file__).parent / "fixtures" / "garmin"


def load_fixture(name: str):
    return json.loads((FIXTURES_PATH / name).read_text())


class StubGarminDataSource:
    def __init__(self, *, sleep_error: Exception | None = None) -> None:
        self.sleep_error = sleep_error
        self.requested_dates: list[date] = []

    def get_activities(self, start_date: date, end_date: date):
        return [load_fixture("running_activity.json")]

    def get_daily_summary(self, metric_date: date):
        self.requested_dates.append(metric_date)
        return load_fixture("daily_summary.json")

    def get_sleep_data(self, metric_date: date):
        if self.sleep_error is not None:
            raise self.sleep_error
        return load_fixture("sleep_day.json")

    def get_hrv_data(self, metric_date: date):
        return load_fixture("hrv_day.json")

    def get_training_readiness(self, metric_date: date):
        return load_fixture("training_readiness_day.json")


def test_full_sync_stores_activities_recovery_metrics_and_one_audit_record():
    service = GarminSyncService(StubGarminDataSource())

    result = service.sync(start_date=date(2026, 6, 14), end_date=date(2026, 6, 14))

    assert result.status == "success"
    assert result.activities_inserted == 1
    assert result.daily_metrics_fetched == 1
    assert result.daily_metrics_inserted == 1

    with SessionFactory() as session:
        activity = session.scalar(select(Activity))
        metric = session.scalar(select(DailyMetric))
        sync_runs = session.scalars(select(SyncRun)).all()

    assert activity is not None
    assert metric is not None
    assert metric.sleep_score == 84
    assert len(sync_runs) == 1
    assert sync_runs[0].status == "success"
    assert sync_runs[0].daily_metrics_inserted == 1


def test_recovery_endpoint_failure_creates_a_partial_sync_without_losing_data():
    service = GarminSyncService(
        StubGarminDataSource(
            sleep_error=GarminIntegrationError("sleep endpoint unavailable"),
        )
    )

    result = service.sync(start_date=date(2026, 6, 14), end_date=date(2026, 6, 14))

    assert result.status == "partial"
    assert result.activities_inserted == 1
    assert result.daily_metrics_inserted == 1
    assert len(result.recovery_errors) == 1

    with SessionFactory() as session:
        metric = session.scalar(select(DailyMetric))
        sync_run = session.get(SyncRun, result.sync_run_id)

    assert metric is not None
    assert metric.sleep_score is None
    assert sync_run is not None
    assert sync_run.status == "partial"
    assert "sleep endpoint unavailable" in (sync_run.error_summary or "")


def test_second_full_sync_updates_existing_activity_and_recovery_records():
    service = GarminSyncService(StubGarminDataSource())

    service.sync(start_date=date(2026, 6, 14), end_date=date(2026, 6, 14))
    result = service.sync(start_date=date(2026, 6, 14), end_date=date(2026, 6, 14))

    assert result.activities_inserted == 0
    assert result.activities_updated == 1
    assert result.daily_metrics_inserted == 0
    assert result.daily_metrics_updated == 1
