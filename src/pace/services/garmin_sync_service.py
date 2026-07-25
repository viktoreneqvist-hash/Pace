"""Application service for a bounded Garmin activity synchronization."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Protocol

from sqlalchemy.orm import Session

from pace.database.models import DailyMetric, SyncRun
from pace.database.session import SessionFactory
from pace.integrations.garmin.client import (
    GarminAuthenticationRequiredError,
    GarminIntegrationError,
    GarminRateLimitError,
)
from pace.integrations.garmin.daily_metrics import normalize_garmin_daily_metric
from pace.integrations.garmin.normalizers import normalize_garmin_activity
from pace.repositories.activity_repository import upsert_activity
from pace.repositories.daily_metric_repository import upsert_daily_metric
from pace.repositories.sync_run_repository import complete_sync_run, create_sync_run


class GarminActivitySource(Protocol):
    """The only Garmin capability required by the activity sync service."""

    def get_activities(
        self,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]: ...


class GarminDataSource(GarminActivitySource, Protocol):
    """Garmin capabilities required for Pace's first complete sync."""

    def get_daily_summary(self, metric_date: date) -> dict[str, Any]: ...

    def get_sleep_data(self, metric_date: date) -> dict[str, Any]: ...

    def get_hrv_data(self, metric_date: date) -> dict[str, Any] | None: ...

    def get_training_readiness(self, metric_date: date) -> list[dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class ActivitySyncResult:
    """The auditable outcome of one successful activity synchronization."""

    sync_run_id: int
    start_date: date
    end_date: date
    activities_fetched: int
    activities_inserted: int
    activities_updated: int


@dataclass(frozen=True, slots=True)
class GarminSyncResult:
    """The full outcome of one activity and recovery synchronization."""

    sync_run_id: int
    status: str
    start_date: date
    end_date: date
    activities_fetched: int
    activities_inserted: int
    activities_updated: int
    daily_metrics_fetched: int
    daily_metrics_inserted: int
    daily_metrics_updated: int
    recovery_errors: tuple[str, ...]


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


class GarminSyncService:
    """Synchronize activities and daily recovery signals under one audit record."""

    def __init__(
        self,
        data_source: GarminDataSource,
        session_factory: Callable[[], Session] = SessionFactory,
    ) -> None:
        self._data_source = data_source
        self._session_factory = session_factory

    def sync(self, *, start_date: date, end_date: date) -> GarminSyncResult:
        """Run one bounded sync with partial recovery support.

        Activities are required for a successful Garmin sync. Recovery metrics
        use independent provider endpoints, so an unavailable device feature or
        one failed endpoint produces a ``partial`` run while valid activities
        and recovery values are still stored.
        """

        sync_run_id = self._create_sync_run(start_date, end_date)

        try:
            provider_activities = self._data_source.get_activities(start_date, end_date)
            if not isinstance(provider_activities, list):
                raise ValueError("Garmin returned an invalid activity list.")

            daily_metrics, recovery_errors = self._fetch_daily_metrics(
                start_date,
                end_date,
            )
            counts = self._store_sync_data(
                sync_run_id=sync_run_id,
                provider_activities=provider_activities,
                daily_metrics=daily_metrics,
                recovery_errors=recovery_errors,
            )
        except Exception as error:
            self._mark_failed(sync_run_id, error)
            raise

        activities_inserted, activities_updated, metrics_inserted, metrics_updated = counts
        return GarminSyncResult(
            sync_run_id=sync_run_id,
            status="partial" if recovery_errors else "success",
            start_date=start_date,
            end_date=end_date,
            activities_fetched=len(provider_activities),
            activities_inserted=activities_inserted,
            activities_updated=activities_updated,
            daily_metrics_fetched=len(daily_metrics),
            daily_metrics_inserted=metrics_inserted,
            daily_metrics_updated=metrics_updated,
            recovery_errors=tuple(recovery_errors),
        )

    def _fetch_daily_metrics(
        self,
        start_date: date,
        end_date: date,
    ) -> tuple[list[DailyMetric], list[str]]:
        daily_metrics: list[DailyMetric] = []
        recovery_errors: list[str] = []
        metric_date = start_date

        while metric_date <= end_date:
            payloads: dict[str, Any] = {}
            endpoint_calls = (
                ("daily summary", self._data_source.get_daily_summary),
                ("sleep", self._data_source.get_sleep_data),
                ("HRV", self._data_source.get_hrv_data),
                ("training readiness", self._data_source.get_training_readiness),
            )

            for endpoint_name, fetch_endpoint in endpoint_calls:
                try:
                    payloads[endpoint_name] = fetch_endpoint(metric_date)
                except GarminIntegrationError as error:
                    recovery_errors.append(f"{metric_date} {endpoint_name}: {error}")
                    if isinstance(
                        error,
                        GarminRateLimitError | GarminAuthenticationRequiredError,
                    ):
                        return daily_metrics, recovery_errors

            if any(payloads.values()):
                try:
                    daily_metrics.append(
                        normalize_garmin_daily_metric(
                            metric_date=metric_date,
                            summary=payloads.get("daily summary"),
                            sleep=payloads.get("sleep"),
                            hrv=payloads.get("HRV"),
                            readiness=payloads.get("training readiness"),
                        )
                    )
                except (AttributeError, TypeError, ValueError) as error:
                    recovery_errors.append(f"{metric_date} normalization: {error}")

            metric_date += timedelta(days=1)

        return daily_metrics, recovery_errors

    def _create_sync_run(self, start_date: date, end_date: date) -> int:
        with self._session_factory.begin() as session:
            sync_run = create_sync_run(
                session,
                provider="garmin",
                requested_start_date=start_date,
                requested_end_date=end_date,
            )
            return sync_run.id

    def _store_sync_data(
        self,
        *,
        sync_run_id: int,
        provider_activities: list[dict[str, Any]],
        daily_metrics: list[DailyMetric],
        recovery_errors: list[str],
    ) -> tuple[int, int, int, int]:
        activities_inserted = 0
        activities_updated = 0
        metrics_inserted = 0
        metrics_updated = 0

        with self._session_factory.begin() as session:
            for provider_activity in provider_activities:
                activity = normalize_garmin_activity(provider_activity)
                _, created = upsert_activity(session, activity)
                activities_inserted += int(created)
                activities_updated += int(not created)

            for daily_metric in daily_metrics:
                _, created = upsert_daily_metric(session, daily_metric)
                metrics_inserted += int(created)
                metrics_updated += int(not created)

            sync_run = session.get(SyncRun, sync_run_id)
            if sync_run is None:
                raise RuntimeError("Sync record was not found.")

            complete_sync_run(
                sync_run,
                status="partial" if recovery_errors else "success",
                activities_fetched=len(provider_activities),
                activities_inserted=activities_inserted,
                activities_updated=activities_updated,
                daily_metrics_fetched=len(daily_metrics),
                daily_metrics_inserted=metrics_inserted,
                daily_metrics_updated=metrics_updated,
                error_summary="; ".join(recovery_errors)[:1000] or None,
            )

        return activities_inserted, activities_updated, metrics_inserted, metrics_updated

    def _mark_failed(self, sync_run_id: int, error: Exception) -> None:
        error_summary = f"{type(error).__name__}: {str(error)[:300]}"

        with self._session_factory.begin() as session:
            sync_run = session.get(SyncRun, sync_run_id)
            if sync_run is not None:
                complete_sync_run(
                    sync_run,
                    status="failed",
                    error_summary=error_summary,
                )
