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
from pace.integrations.garmin.daily_metrics import (
    HRV_SOURCE,
    SLEEP_SOURCE,
    SUMMARY_SOURCE,
    TRAINING_READINESS_SOURCE,
    fields_for_successful_sources,
    normalize_garmin_daily_metric,
    validate_garmin_daily_payload,
)
from pace.integrations.garmin.normalizers import normalize_garmin_activity
from pace.repositories.activity_repository import upsert_activity
from pace.repositories.daily_metric_repository import upsert_daily_metric
from pace.repositories.sync_run_repository import complete_sync_run, create_sync_run


MAX_SYNC_DAYS = 7


def validate_sync_window(start_date: date, end_date: date) -> None:
    """Reject invalid or unexpectedly large provider request windows."""

    day_count = (end_date - start_date).days + 1
    if day_count < 1:
        raise ValueError("Sync end_date cannot be earlier than start_date.")
    if day_count > MAX_SYNC_DAYS:
        raise ValueError(f"A Garmin sync may include at most {MAX_SYNC_DAYS} days.")


class GarminDataSource(Protocol):
    """Garmin capabilities required for Pace's first complete sync."""

    def get_activities(
        self,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]: ...

    def get_daily_summary(self, metric_date: date) -> dict[str, Any]: ...

    def get_sleep_data(self, metric_date: date) -> dict[str, Any]: ...

    def get_hrv_data(self, metric_date: date) -> dict[str, Any] | None: ...

    def get_training_readiness(self, metric_date: date) -> list[dict[str, Any]]: ...


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
    recovery_stop_reason: str | None = None


@dataclass(frozen=True, slots=True)
class DailyMetricSyncItem:
    """A normalized day plus the provider endpoints that completed."""

    metric: DailyMetric
    successful_sources: frozenset[str]


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

        validate_sync_window(start_date, end_date)
        sync_run_id = self._create_sync_run(start_date, end_date)
        provider_activities: list[dict[str, Any]] = []
        daily_metric_items: list[DailyMetricSyncItem] = []
        recovery_errors: list[str] = []
        recovery_stop_reason: str | None = None

        try:
            provider_activities = self._data_source.get_activities(start_date, end_date)
            if not isinstance(provider_activities, list):
                raise ValueError("Garmin returned an invalid activity list.")

            (
                daily_metric_items,
                recovery_errors,
                recovery_stop_reason,
            ) = self._fetch_daily_metrics(start_date, end_date)
            counts = self._store_sync_data(
                sync_run_id=sync_run_id,
                provider_activities=provider_activities,
                daily_metric_items=daily_metric_items,
                recovery_errors=recovery_errors,
            )
        except Exception as error:
            self._mark_failed(
                sync_run_id,
                error,
                activities_fetched=len(provider_activities),
                daily_metrics_fetched=len(daily_metric_items),
            )
            raise

        activities_inserted, activities_updated, metrics_inserted, metrics_updated = (
            counts
        )
        return GarminSyncResult(
            sync_run_id=sync_run_id,
            status="partial" if recovery_errors else "success",
            start_date=start_date,
            end_date=end_date,
            activities_fetched=len(provider_activities),
            activities_inserted=activities_inserted,
            activities_updated=activities_updated,
            daily_metrics_fetched=len(daily_metric_items),
            daily_metrics_inserted=metrics_inserted,
            daily_metrics_updated=metrics_updated,
            recovery_errors=tuple(recovery_errors),
            recovery_stop_reason=recovery_stop_reason,
        )

    def _fetch_daily_metrics(
        self,
        start_date: date,
        end_date: date,
    ) -> tuple[list[DailyMetricSyncItem], list[str], str | None]:
        daily_metric_items: list[DailyMetricSyncItem] = []
        recovery_errors: list[str] = []
        stop_reason: str | None = None
        metric_date = start_date

        while metric_date <= end_date:
            payloads: dict[str, Any] = {}
            successful_sources: set[str] = set()
            endpoint_calls = (
                (SUMMARY_SOURCE, "daily summary", self._data_source.get_daily_summary),
                (SLEEP_SOURCE, "sleep", self._data_source.get_sleep_data),
                (HRV_SOURCE, "HRV", self._data_source.get_hrv_data),
                (
                    TRAINING_READINESS_SOURCE,
                    "training readiness",
                    self._data_source.get_training_readiness,
                ),
            )

            for source_name, endpoint_name, fetch_endpoint in endpoint_calls:
                try:
                    payload = fetch_endpoint(metric_date)
                    validate_garmin_daily_payload(source_name, payload)
                    payloads[source_name] = payload
                    successful_sources.add(source_name)
                except GarminIntegrationError as error:
                    recovery_errors.append(f"{metric_date} {endpoint_name}: {error}")
                    if isinstance(error, GarminRateLimitError):
                        stop_reason = "rate_limit"
                        break
                    if isinstance(error, GarminAuthenticationRequiredError):
                        stop_reason = "authentication"
                        break
                except ValueError as error:
                    recovery_errors.append(f"{metric_date} {endpoint_name}: {error}")

            if successful_sources:
                try:
                    daily_metric_items.append(
                        DailyMetricSyncItem(
                            metric=normalize_garmin_daily_metric(
                                metric_date=metric_date,
                                summary=payloads.get(SUMMARY_SOURCE),
                                sleep=payloads.get(SLEEP_SOURCE),
                                hrv=payloads.get(HRV_SOURCE),
                                readiness=payloads.get(TRAINING_READINESS_SOURCE),
                            ),
                            successful_sources=frozenset(successful_sources),
                        )
                    )
                except (AttributeError, TypeError, ValueError) as error:
                    recovery_errors.append(f"{metric_date} normalization: {error}")

            if stop_reason is not None:
                break

            metric_date += timedelta(days=1)

        return daily_metric_items, recovery_errors, stop_reason

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
        daily_metric_items: list[DailyMetricSyncItem],
        recovery_errors: list[str],
    ) -> tuple[int, int, int, int]:
        activities_inserted = 0
        activities_updated = 0
        metrics_inserted = 0
        metrics_updated = 0

        with self._session_factory.begin() as session:
            for provider_activity in provider_activities:
                activity = normalize_garmin_activity(provider_activity)
                _, created, changed = upsert_activity(session, activity)
                activities_inserted += int(created)
                activities_updated += int(changed)

            for item in daily_metric_items:
                _, created, changed = upsert_daily_metric(
                    session,
                    item.metric,
                    fields_to_update=fields_for_successful_sources(
                        item.successful_sources
                    ),
                    raw_payload_keys_to_update=item.successful_sources,
                )
                metrics_inserted += int(created)
                metrics_updated += int(changed)

            sync_run = session.get(SyncRun, sync_run_id)
            if sync_run is None:
                raise RuntimeError("Sync record was not found.")

            complete_sync_run(
                sync_run,
                status="partial" if recovery_errors else "success",
                activities_fetched=len(provider_activities),
                activities_inserted=activities_inserted,
                activities_updated=activities_updated,
                daily_metrics_fetched=len(daily_metric_items),
                daily_metrics_inserted=metrics_inserted,
                daily_metrics_updated=metrics_updated,
                error_summary="; ".join(recovery_errors)[:1000] or None,
            )

        return (
            activities_inserted,
            activities_updated,
            metrics_inserted,
            metrics_updated,
        )

    def _mark_failed(
        self,
        sync_run_id: int,
        error: Exception,
        *,
        activities_fetched: int = 0,
        daily_metrics_fetched: int = 0,
    ) -> None:
        error_summary = f"{type(error).__name__}: {str(error)[:300]}"

        with self._session_factory.begin() as session:
            sync_run = session.get(SyncRun, sync_run_id)
            if sync_run is not None:
                complete_sync_run(
                    sync_run,
                    status="failed",
                    activities_fetched=activities_fetched,
                    daily_metrics_fetched=daily_metrics_fetched,
                    error_summary=error_summary,
                )
