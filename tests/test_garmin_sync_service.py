import json
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select

from pace.database.models import Activity, SyncRun
from pace.database.session import SessionFactory
from pace.services.garmin_sync_service import GarminActivitySyncService


FIXTURES_PATH = Path(__file__).parent / "fixtures" / "garmin"


class StubGarminActivitySource:
    def __init__(self, activities):
        self.activities = activities
        self.requested_window: tuple[date, date] | None = None

    def get_activities(self, start_date: date, end_date: date):
        self.requested_window = (start_date, end_date)
        if isinstance(self.activities, Exception):
            raise self.activities
        return self.activities


def load_running_activity() -> dict:
    return json.loads((FIXTURES_PATH / "running_activity.json").read_text())


def test_sync_stores_normalized_activities_and_an_audit_record():
    source = StubGarminActivitySource([load_running_activity()])
    service = GarminActivitySyncService(source)

    result = service.sync_activities(
        start_date=date(2026, 6, 8),
        end_date=date(2026, 6, 14),
    )

    assert source.requested_window == (date(2026, 6, 8), date(2026, 6, 14))
    assert result.activities_fetched == 1
    assert result.activities_inserted == 1
    assert result.activities_updated == 0

    with SessionFactory() as session:
        activity = session.scalar(select(Activity))
        sync_run = session.get(SyncRun, result.sync_run_id)

    assert activity is not None
    assert activity.provider_activity_id == "mock-garmin-1"
    assert sync_run is not None
    assert sync_run.status == "success"
    assert sync_run.activities_inserted == 1


def test_second_sync_updates_instead_of_creating_a_duplicate():
    source = StubGarminActivitySource([load_running_activity()])
    service = GarminActivitySyncService(source)

    service.sync_activities(start_date=date(2026, 6, 8), end_date=date(2026, 6, 14))
    second_result = service.sync_activities(
        start_date=date(2026, 6, 8),
        end_date=date(2026, 6, 14),
    )

    assert second_result.activities_inserted == 0
    assert second_result.activities_updated == 1

    with SessionFactory() as session:
        activities = session.scalars(select(Activity)).all()

    assert len(activities) == 1


def test_failed_sync_keeps_activities_atomic_and_records_failure():
    service = GarminActivitySyncService(StubGarminActivitySource(RuntimeError("offline")))

    with pytest.raises(RuntimeError, match="offline"):
        service.sync_activities(start_date=date(2026, 6, 8), end_date=date(2026, 6, 14))

    with SessionFactory() as session:
        activities = session.scalars(select(Activity)).all()
        sync_run = session.scalar(select(SyncRun))

    assert activities == []
    assert sync_run is not None
    assert sync_run.status == "failed"
    assert sync_run.error_summary == "RuntimeError: offline"
