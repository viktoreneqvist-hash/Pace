"""Bounded Garmin detail import and read-only race-evidence history."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Protocol

from sqlalchemy.orm import Session

from pace.capacity.analysis import INCLUDED_SPORT_TYPES
from pace.database.models import (
    Activity,
    ActivityPerformanceDetail,
    PerformanceEvidence,
    PerformanceSyncRun,
    Race,
)
from pace.database.session import SessionFactory, session_scope
from pace.integrations.garmin.client import (
    GarminAuthenticationRequiredError,
    GarminIntegrationError,
    GarminRateLimitError,
)
from pace.integrations.garmin.performance import normalize_garmin_performance_detail
from pace.performance.models import (
    DetailedActivityFact,
    PerformanceDetailCoverage,
    PerformanceHistory,
    RaceEvidenceFact,
)
from pace.repositories.activity_performance_detail_repository import (
    get_detail_for_activity,
    get_details_for_activities,
    upsert_activity_performance_detail,
)
from pace.repositories.activity_repository import (
    get_activities_in_date_range,
    get_activity_by_provider_id,
)
from pace.repositories.performance_evidence_repository import (
    create_performance_evidence,
    get_evidence_for_activities,
    get_evidence_for_activity,
    get_evidence_for_race,
)
from pace.repositories.performance_sync_run_repository import (
    complete_performance_sync_run,
    create_performance_sync_run,
)
from pace.repositories.race_repository import get_race_by_id
from pace.services.garmin_sync_service import validate_sync_window
from pace.timezones import athlete_local_date


PERFORMANCE_HISTORY_DAYS = 84


class GarminPerformanceDataSource(Protocol):
    """Only the two provider calls needed for privacy-minimized detail import."""

    def get_activity_performance_detail(self, activity_id: str) -> dict[str, Any]: ...

    def get_activity_splits(self, activity_id: str) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class PerformanceSyncResult:
    """Auditable result from one at-most-seven-day detail import."""

    sync_run_id: int
    status: str
    start_date: date
    end_date: date
    candidate_activities: int
    details_fetched: int
    details_inserted: int
    details_updated: int
    errors: tuple[str, ...]
    stop_reason: str | None = None


class PerformanceHistoryService:
    """Keep detailed Garmin evidence local, bounded, and independently auditable."""

    def __init__(
        self,
        data_source: GarminPerformanceDataSource | None = None,
        session_factory: Callable[[], Session] = SessionFactory,
    ) -> None:
        self._data_source = data_source
        self._session_factory = session_factory

    def sync_details(
        self, *, start_date: date, end_date: date
    ) -> PerformanceSyncResult:
        """Fetch only existing local run/ride activities in one safe calendar batch."""

        if self._data_source is None:
            raise RuntimeError("A Garmin performance data source is required for sync.")
        validate_sync_window(start_date, end_date)
        candidates = self._candidates(start_date=start_date, end_date=end_date)
        sync_run_id = self._create_sync_run(
            start_date=start_date,
            end_date=end_date,
            candidate_activities=len(candidates),
        )
        errors: list[str] = []
        details_fetched = 0
        details_inserted = 0
        details_updated = 0
        stop_reason: str | None = None

        try:
            for activity in candidates:
                try:
                    detail_payload = self._data_source.get_activity_performance_detail(
                        activity.provider_activity_id
                    )
                    splits_payload = self._data_source.get_activity_splits(
                        activity.provider_activity_id
                    )
                    normalized = normalize_garmin_performance_detail(
                        detail_payload, splits_payload
                    )
                    created, changed = self._store_detail(
                        activity_id=activity.id,
                        normalized=normalized,
                    )
                    details_fetched += 1
                    details_inserted += int(created)
                    details_updated += int(changed)
                except GarminIntegrationError as error:
                    errors.append(f"{activity.provider_activity_id}: {error}")
                    if isinstance(error, GarminRateLimitError):
                        stop_reason = "rate_limit"
                        break
                    if isinstance(error, GarminAuthenticationRequiredError):
                        stop_reason = "authentication"
                        break
                except ValueError as error:
                    errors.append(f"{activity.provider_activity_id}: {error}")

            self._complete_sync_run(
                sync_run_id=sync_run_id,
                status="partial" if errors else "success",
                details_fetched=details_fetched,
                details_inserted=details_inserted,
                details_updated=details_updated,
                errors=errors,
            )
        except Exception as error:
            self._complete_sync_run(
                sync_run_id=sync_run_id,
                status="failed",
                details_fetched=details_fetched,
                details_inserted=details_inserted,
                details_updated=details_updated,
                errors=[f"{type(error).__name__}: {str(error)[:300]}"],
            )
            raise

        return PerformanceSyncResult(
            sync_run_id=sync_run_id,
            status="partial" if errors else "success",
            start_date=start_date,
            end_date=end_date,
            candidate_activities=len(candidates),
            details_fetched=details_fetched,
            details_inserted=details_inserted,
            details_updated=details_updated,
            errors=tuple(errors),
            stop_reason=stop_reason,
        )

    def link_race_evidence(
        self, *, garmin_activity_id: str, race_id: int
    ) -> PerformanceEvidence:
        """Link one detailed Garmin result to a race only after athlete confirmation."""

        with session_scope() as session:
            activity = get_activity_by_provider_id(session, "garmin", garmin_activity_id)
            if activity is None:
                raise ValueError("No imported Garmin activity has that activity id.")
            race = get_race_by_id(session, race_id)
            if race is None:
                raise ValueError(f"No race exists with id {race_id}.")
            if activity.sport_type not in INCLUDED_SPORT_TYPES:
                raise ValueError("Only normalized run and ride activities can be race evidence.")
            if activity.sport_type != race.sport_type:
                raise ValueError("The Garmin activity sport must match the race sport.")
            if athlete_local_date(activity.start_time) != race.race_date:
                raise ValueError(
                    "The Garmin activity date must match the explicitly stored race date."
                )
            if get_detail_for_activity(session, activity_id=activity.id) is None:
                raise ValueError(
                    "Import activity details before linking this Garmin activity as race evidence."
                )

            existing_activity = get_evidence_for_activity(session, activity_id=activity.id)
            existing_race = get_evidence_for_race(session, race_id=race.id)
            if existing_activity is not None and existing_activity.race_id == race.id:
                return existing_activity
            if existing_activity is not None:
                raise ValueError("This Garmin activity is already linked to other evidence.")
            if existing_race is not None:
                raise ValueError("This race is already linked to another Garmin activity.")
            return create_performance_evidence(
                session,
                PerformanceEvidence(
                    activity_id=activity.id,
                    evidence_type="race",
                    race_id=race.id,
                ),
            )

    def get_history(self, *, end_date: date) -> PerformanceHistory:
        """Return twelve-week local detail coverage and explicitly linked race facts."""

        start_date = end_date - timedelta(days=PERFORMANCE_HISTORY_DAYS - 1)
        with session_scope() as session:
            activities = [
                activity
                for activity in get_activities_in_date_range(
                    session, start_date=start_date, end_date=end_date
                )
                if activity.sport_type in INCLUDED_SPORT_TYPES
            ]
            activity_ids = [activity.id for activity in activities]
            details = get_details_for_activities(session, activity_ids=activity_ids)
            evidence = get_evidence_for_activities(session, activity_ids=activity_ids)
            races = {
                evidence_item.race_id: session.get(Race, evidence_item.race_id)
                for evidence_item in evidence.values()
                if evidence_item.evidence_type == "race" and evidence_item.race_id is not None
            }

        detailed_activities = tuple(
            DetailedActivityFact(
                garmin_activity_id=activity.provider_activity_id,
                activity_date=athlete_local_date(activity.start_time),
                sport_type=activity.sport_type,
                split_count=len(details[activity.id].splits),
                duration_seconds=details[activity.id].duration_seconds,
                distance_meters=details[activity.id].distance_meters,
            )
            for activity in activities
            if activity.id in details
        )
        race_evidence = tuple(
            self._race_evidence_fact(
                activity=activity,
                detail=details[activity.id],
                evidence=evidence[activity.id],
                race=races[evidence[activity.id].race_id],
            )
            for activity in activities
            if activity.id in details
            and activity.id in evidence
            and evidence[activity.id].evidence_type == "race"
            and evidence[activity.id].race_id in races
            and races[evidence[activity.id].race_id] is not None
        )
        coverage = PerformanceDetailCoverage(
            start_date=start_date,
            end_date=end_date,
            eligible_activities=len(activities),
            detailed_activities=len(details),
            missing_details=len(activities) - len(details),
        )
        return PerformanceHistory(
            as_of_date=end_date,
            detail_coverage=coverage,
            detailed_activities=detailed_activities,
            race_evidence=race_evidence,
            limitations=_history_limitations(coverage, race_evidence),
        )

    def _candidates(self, *, start_date: date, end_date: date) -> list[Activity]:
        with self._session_factory() as session:
            return [
                activity
                for activity in get_activities_in_date_range(
                    session, start_date=start_date, end_date=end_date
                )
                if activity.sport_type in INCLUDED_SPORT_TYPES
            ]

    def _create_sync_run(self, *, start_date: date, end_date: date, candidate_activities: int) -> int:
        with self._session_factory.begin() as session:
            sync_run = create_performance_sync_run(
                session,
                provider="garmin",
                requested_start_date=start_date,
                requested_end_date=end_date,
                candidate_activities=candidate_activities,
            )
            return sync_run.id

    def _store_detail(self, *, activity_id: int, normalized) -> tuple[bool, bool]:
        with self._session_factory.begin() as session:
            _, created, changed = upsert_activity_performance_detail(
                session,
                ActivityPerformanceDetail(
                    activity_id=activity_id,
                    duration_seconds=normalized.duration_seconds,
                    distance_meters=normalized.distance_meters,
                    average_heart_rate=normalized.average_heart_rate,
                    maximum_heart_rate=normalized.maximum_heart_rate,
                    average_speed_mps=normalized.average_speed_mps,
                    average_cadence=normalized.average_cadence,
                    average_power=normalized.average_power,
                    splits=normalized.splits,
                ),
            )
            return created, changed

    def _complete_sync_run(
        self,
        *,
        sync_run_id: int,
        status: str,
        details_fetched: int,
        details_inserted: int,
        details_updated: int,
        errors: list[str],
    ) -> None:
        with self._session_factory.begin() as session:
            sync_run = session.get(PerformanceSyncRun, sync_run_id)
            if sync_run is None:
                raise RuntimeError("Performance detail sync record was not found.")
            complete_performance_sync_run(
                sync_run,
                status=status,
                details_fetched=details_fetched,
                details_inserted=details_inserted,
                details_updated=details_updated,
                error_summary="; ".join(errors)[:1000] or None,
            )

    @staticmethod
    def _race_evidence_fact(
        *,
        activity: Activity,
        detail: ActivityPerformanceDetail,
        evidence: PerformanceEvidence,
        race: Race,
    ) -> RaceEvidenceFact:
        return RaceEvidenceFact(
            garmin_activity_id=activity.provider_activity_id,
            activity_date=athlete_local_date(activity.start_time),
            sport_type=activity.sport_type,
            race_id=race.id,
            race_name=race.name,
            race_date=race.race_date,
            race_distance_meters=race.distance_meters,
            duration_seconds=detail.duration_seconds,
            distance_meters=detail.distance_meters,
            average_speed_mps=detail.average_speed_mps,
            average_heart_rate=detail.average_heart_rate,
            average_power=detail.average_power,
            split_count=len(detail.splits),
        )


def _history_limitations(
    coverage: PerformanceDetailCoverage,
    race_evidence: tuple[RaceEvidenceFact, ...],
) -> tuple[str, ...]:
    limitations: list[str] = []
    if coverage.eligible_activities == 0:
        limitations.append("no_eligible_run_or_ride_activities_in_last_12_weeks")
    elif coverage.missing_details:
        limitations.append("activity_detail_import_incomplete")
    if not race_evidence:
        limitations.append("no_explicit_race_evidence")
    limitations.extend(
        (
            "benchmark_protocols_require_owner_decision",
            "performance_targets_pending_j2c",
        )
    )
    return tuple(limitations)
