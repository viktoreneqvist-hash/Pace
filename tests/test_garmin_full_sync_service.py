import json
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select

from pace.database.models import Activity, DailyMetric, SyncRun
from pace.database.session import SessionFactory
from pace.integrations.garmin.client import (
    GarminAuthenticationRequiredError,
    GarminIntegrationError,
    GarminRateLimitError,
)
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


def test_identical_second_full_sync_reports_no_changed_records():
    service = GarminSyncService(StubGarminDataSource())

    service.sync(start_date=date(2026, 6, 14), end_date=date(2026, 6, 14))
    result = service.sync(start_date=date(2026, 6, 14), end_date=date(2026, 6, 14))

    assert result.activities_inserted == 0
    assert result.activities_updated == 0
    assert result.daily_metrics_inserted == 0
    assert result.daily_metrics_updated == 0


def test_partial_resync_preserves_values_from_an_endpoint_that_now_fails():
    GarminSyncService(StubGarminDataSource()).sync(
        start_date=date(2026, 6, 14),
        end_date=date(2026, 6, 14),
    )

    result = GarminSyncService(
        StubGarminDataSource(
            sleep_error=GarminIntegrationError("sleep endpoint unavailable"),
        )
    ).sync(
        start_date=date(2026, 6, 14),
        end_date=date(2026, 6, 14),
    )

    with SessionFactory() as session:
        metric = session.scalar(select(DailyMetric))

    assert result.status == "partial"
    assert result.daily_metrics_updated == 0
    assert metric is not None
    assert metric.sleep_score == 84
    assert metric.sleep_duration_seconds == 28_800
    assert "sleep" in metric.raw_payload


def test_rate_limit_saves_endpoints_already_fetched_for_the_current_day():
    result = GarminSyncService(
        StubGarminDataSource(
            sleep_error=GarminRateLimitError("wait"),
        )
    ).sync(
        start_date=date(2026, 6, 14),
        end_date=date(2026, 6, 14),
    )

    with SessionFactory() as session:
        metric = session.scalar(select(DailyMetric))

    assert result.status == "partial"
    assert result.recovery_stop_reason == "rate_limit"
    assert result.daily_metrics_inserted == 1
    assert metric is not None
    assert metric.resting_heart_rate == 46
    assert metric.sleep_score is None
    assert set(metric.raw_payload) == {"summary"}


def test_expired_session_saves_current_day_then_stops_the_remaining_range():
    result = GarminSyncService(
        StubGarminDataSource(
            sleep_error=GarminAuthenticationRequiredError("login required"),
        )
    ).sync(
        start_date=date(2026, 6, 14),
        end_date=date(2026, 6, 16),
    )

    with SessionFactory() as session:
        metrics = session.scalars(select(DailyMetric)).all()

    assert result.status == "partial"
    assert result.recovery_stop_reason == "authentication"
    assert result.daily_metrics_fetched == 1
    assert len(metrics) == 1
    assert metrics[0].resting_heart_rate == 46


def test_successful_empty_endpoints_clear_an_older_daily_snapshot():
    GarminSyncService(StubGarminDataSource()).sync(
        start_date=date(2026, 6, 14),
        end_date=date(2026, 6, 14),
    )

    class EmptyRecoverySource(StubGarminDataSource):
        def get_daily_summary(self, metric_date: date):
            return {}

        def get_sleep_data(self, metric_date: date):
            return {}

        def get_hrv_data(self, metric_date: date):
            return None

        def get_training_readiness(self, metric_date: date):
            return []

    result = GarminSyncService(EmptyRecoverySource()).sync(
        start_date=date(2026, 6, 14),
        end_date=date(2026, 6, 14),
    )

    with SessionFactory() as session:
        metric = session.scalar(select(DailyMetric))

    assert result.status == "success"
    assert result.daily_metrics_updated == 1
    assert metric is not None
    assert metric.sleep_score is None
    assert metric.hrv_value is None
    assert metric.resting_heart_rate is None
    assert metric.raw_payload == {}


def test_malformed_endpoint_payload_preserves_its_older_daily_snapshot():
    GarminSyncService(StubGarminDataSource()).sync(
        start_date=date(2026, 6, 14),
        end_date=date(2026, 6, 14),
    )

    class MalformedSleepSource(StubGarminDataSource):
        def get_sleep_data(self, metric_date: date):
            return ["not", "a", "sleep", "object"]

    result = GarminSyncService(MalformedSleepSource()).sync(
        start_date=date(2026, 6, 14),
        end_date=date(2026, 6, 14),
    )

    with SessionFactory() as session:
        metric = session.scalar(select(DailyMetric))

    assert result.status == "partial"
    assert result.daily_metrics_updated == 0
    assert metric is not None
    assert metric.sleep_score == 84
    assert metric.sleep_duration_seconds == 28_800
    assert isinstance(metric.raw_payload["sleep"], dict)


def test_malformed_second_activity_rolls_back_the_entire_data_batch():
    class SourceWithMalformedSecondActivity(StubGarminDataSource):
        def get_activities(self, start_date: date, end_date: date):
            malformed = load_fixture("running_activity.json")
            malformed["activityId"] = "missing-duration"
            malformed["summaryDTO"].pop("duration")
            return [load_fixture("running_activity.json"), malformed]

    with pytest.raises(ValueError, match="missing duration"):
        GarminSyncService(SourceWithMalformedSecondActivity()).sync(
            start_date=date(2026, 6, 14),
            end_date=date(2026, 6, 14),
        )

    with SessionFactory() as session:
        activities = session.scalars(select(Activity)).all()
        daily_metrics = session.scalars(select(DailyMetric)).all()
        sync_run = session.scalar(select(SyncRun))

    assert activities == []
    assert daily_metrics == []
    assert sync_run is not None
    assert sync_run.status == "failed"
    assert sync_run.activities_fetched == 2
    assert sync_run.daily_metrics_fetched == 1


def test_service_rejects_an_unbounded_sync_before_calling_garmin():
    source = StubGarminDataSource()

    with pytest.raises(ValueError, match="at most 7 days"):
        GarminSyncService(source).sync(
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 8),
        )

    assert source.requested_dates == []

    with SessionFactory() as session:
        assert session.scalar(select(SyncRun)) is None
