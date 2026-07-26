"""Audit persistence for bounded activity-performance detail imports."""

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from pace.database.models import PerformanceSyncRun


def create_performance_sync_run(
    session: Session,
    *,
    provider: str,
    requested_start_date: date,
    requested_end_date: date,
    candidate_activities: int,
) -> PerformanceSyncRun:
    sync_run = PerformanceSyncRun(
        provider=provider,
        requested_start_date=requested_start_date,
        requested_end_date=requested_end_date,
        candidate_activities=candidate_activities,
    )
    session.add(sync_run)
    session.flush()
    return sync_run


def complete_performance_sync_run(
    sync_run: PerformanceSyncRun,
    *,
    status: str,
    details_fetched: int,
    details_inserted: int,
    details_updated: int,
    error_summary: str | None = None,
) -> PerformanceSyncRun:
    sync_run.completed_at = datetime.now(UTC)
    sync_run.status = status
    sync_run.details_fetched = details_fetched
    sync_run.details_inserted = details_inserted
    sync_run.details_updated = details_updated
    sync_run.error_summary = error_summary
    return sync_run
