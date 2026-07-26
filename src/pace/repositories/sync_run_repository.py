"""Persistence operations for synchronization audit records."""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pace.database.models import SyncRun


def get_latest_completed_sync_run(session: Session) -> SyncRun | None:
    """Return the most recently completed provider synchronization attempt."""

    statement = (
        select(SyncRun)
        .where(SyncRun.completed_at.is_not(None))
        .order_by(SyncRun.completed_at.desc(), SyncRun.id.desc())
        .limit(1)
    )
    return session.scalar(statement)


def get_completed_sync_runs_through_date(
    session: Session,
    *,
    provider: str,
    end_date: date,
) -> list[SyncRun]:
    """Return successful or partial completed coverage windows through one date."""

    statement = (
        select(SyncRun)
        .where(
            SyncRun.provider == provider,
            SyncRun.status.in_(("success", "partial")),
            SyncRun.completed_at.is_not(None),
            SyncRun.requested_start_date.is_not(None),
            SyncRun.requested_end_date.is_not(None),
            SyncRun.requested_end_date <= end_date,
        )
        .order_by(SyncRun.requested_start_date, SyncRun.requested_end_date, SyncRun.id)
    )
    return list(session.scalars(statement))


def create_sync_run(
    session: Session,
    provider: str,
    requested_start_date=None,
    requested_end_date=None,
) -> SyncRun:
    """Record the start of a provider synchronization."""

    sync_run = SyncRun(
        provider=provider,
        requested_start_date=requested_start_date,
        requested_end_date=requested_end_date,
    )
    session.add(sync_run)
    session.flush()
    return sync_run


def complete_sync_run(
    sync_run: SyncRun,
    *,
    status: str,
    activities_fetched: int = 0,
    activities_inserted: int = 0,
    activities_updated: int = 0,
    daily_metrics_fetched: int = 0,
    daily_metrics_inserted: int = 0,
    daily_metrics_updated: int = 0,
    error_summary: str | None = None,
) -> SyncRun:
    """Finalize a synchronization record with its outcome."""

    sync_run.completed_at = datetime.now(UTC)
    sync_run.status = status
    sync_run.activities_fetched = activities_fetched
    sync_run.activities_inserted = activities_inserted
    sync_run.activities_updated = activities_updated
    sync_run.daily_metrics_fetched = daily_metrics_fetched
    sync_run.daily_metrics_inserted = daily_metrics_inserted
    sync_run.daily_metrics_updated = daily_metrics_updated
    sync_run.error_summary = error_summary
    return sync_run
