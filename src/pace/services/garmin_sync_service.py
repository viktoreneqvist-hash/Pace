"""Application service for a bounded Garmin activity synchronization."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from sqlalchemy.orm import Session

from pace.database.models import SyncRun
from pace.database.session import SessionFactory
from pace.integrations.garmin.normalizers import normalize_garmin_activity
from pace.repositories.activity_repository import upsert_activity
from pace.repositories.sync_run_repository import complete_sync_run, create_sync_run


class GarminActivitySource(Protocol):
    """The only Garmin capability required by the activity sync service."""

    def get_activities(
        self,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class ActivitySyncResult:
    """The auditable outcome of one successful activity synchronization."""

    sync_run_id: int
    start_date: date
    end_date: date
    activities_fetched: int
    activities_inserted: int
    activities_updated: int


class GarminActivitySyncService:
    """Fetch, normalize, and atomically store a Garmin activity window."""

    def __init__(
        self,
        activity_source: GarminActivitySource,
        session_factory: Callable[[], Session] = SessionFactory,
    ) -> None:
        self._activity_source = activity_source
        self._session_factory = session_factory

    def sync_activities(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> ActivitySyncResult:
        """Synchronize activities and leave a completed audit record.

        Provider payloads are stored only if the entire requested activity
        window can be normalized and written. A failed sync therefore cannot
        leave a half-imported date range behind.
        """

        sync_run_id = self._create_sync_run(start_date, end_date)

        try:
            provider_activities = self._activity_source.get_activities(
                start_date,
                end_date,
            )

            if not isinstance(provider_activities, list):
                raise ValueError("Garmin returned an invalid activity list.")

            inserted, updated = self._store_activities(
                sync_run_id=sync_run_id,
                provider_activities=provider_activities,
            )
        except Exception as error:
            self._mark_failed(sync_run_id, error)
            raise

        return ActivitySyncResult(
            sync_run_id=sync_run_id,
            start_date=start_date,
            end_date=end_date,
            activities_fetched=len(provider_activities),
            activities_inserted=inserted,
            activities_updated=updated,
        )

    def _create_sync_run(self, start_date: date, end_date: date) -> int:
        with self._session_factory.begin() as session:
            sync_run = create_sync_run(
                session,
                provider="garmin",
                requested_start_date=start_date,
                requested_end_date=end_date,
            )
            return sync_run.id

    def _store_activities(
        self,
        *,
        sync_run_id: int,
        provider_activities: list[dict[str, Any]],
    ) -> tuple[int, int]:
        inserted = 0
        updated = 0

        with self._session_factory.begin() as session:
            for provider_activity in provider_activities:
                activity = normalize_garmin_activity(provider_activity)
                _, created = upsert_activity(session, activity)
                inserted += int(created)
                updated += int(not created)

            sync_run = session.get(SyncRun, sync_run_id)
            if sync_run is None:
                raise RuntimeError("Sync record was not found.")

            complete_sync_run(
                sync_run,
                status="success",
                activities_fetched=len(provider_activities),
                activities_inserted=inserted,
                activities_updated=updated,
            )

        return inserted, updated

    def _mark_failed(self, sync_run_id: int, error: Exception) -> None:
        """Persist a brief diagnostic without copying provider data or secrets."""

        error_summary = f"{type(error).__name__}: {str(error)[:300]}"

        with self._session_factory.begin() as session:
            sync_run = session.get(SyncRun, sync_run_id)
            if sync_run is not None:
                complete_sync_run(
                    sync_run,
                    status="failed",
                    error_summary=error_summary,
                )
