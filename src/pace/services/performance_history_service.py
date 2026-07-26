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
    BenchmarkEvidenceFact,
    DetailedActivityFact,
    PerformanceDetailCoverage,
    PerformanceHistory,
    PerformanceReadiness,
    RaceEvidenceFact,
    SportPerformanceReadiness,
)
from pace.performance.protocols import (
    BENCHMARK_PROTOCOLS,
    validate_benchmark_activity,
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
from pace.services.plan_readiness_service import PlanReadinessService
from pace.timezones import athlete_local_date


PERFORMANCE_HISTORY_DAYS = 84
RECENT_SPORT_ACTIVITY_DAYS = 14
REQUIRED_RECENT_SPORT_ACTIVITIES = 2


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

    def mark_benchmark_evidence(
        self,
        *,
        garmin_activity_id: str,
        protocol_key: str,
    ) -> PerformanceEvidence:
        """Store an athlete-confirmed benchmark only when Garmin facts validate it."""

        protocol = BENCHMARK_PROTOCOLS.get(protocol_key)
        if protocol is None:
            raise ValueError(f"Unsupported Pace benchmark protocol: {protocol_key}.")
        with session_scope() as session:
            activity = get_activity_by_provider_id(session, "garmin", garmin_activity_id)
            if activity is None:
                raise ValueError("No imported Garmin activity has that activity id.")
            detail = get_detail_for_activity(session, activity_id=activity.id)
            if detail is None:
                raise ValueError(
                    "Import activity details before marking this Garmin activity as a benchmark."
                )
            existing = get_evidence_for_activity(session, activity_id=activity.id)
            if existing is not None:
                if (
                    existing.evidence_type == "benchmark"
                    and existing.benchmark_protocol == protocol_key
                ):
                    return existing
                raise ValueError("This Garmin activity is already linked to other evidence.")
            validate_benchmark_activity(
                protocol=protocol,
                sport_type=activity.sport_type,
                distance_meters=activity.distance_meters,
                detail=detail,
            )
            return create_performance_evidence(
                session,
                PerformanceEvidence(
                    activity_id=activity.id,
                    evidence_type="benchmark",
                    benchmark_protocol=protocol_key,
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
            self._detailed_activity_fact(
                activity=activity,
                detail=details[activity.id],
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
        benchmark_evidence = tuple(
            self._benchmark_evidence_fact(
                activity=activity,
                detail=details[activity.id],
                evidence=evidence[activity.id],
            )
            for activity in activities
            if activity.id in details
            and activity.id in evidence
            and evidence[activity.id].evidence_type == "benchmark"
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
            benchmark_evidence=benchmark_evidence,
            limitations=_history_limitations(
                coverage,
                race_evidence,
                benchmark_evidence,
            ),
        )

    def get_readiness(self, *, end_date: date) -> PerformanceReadiness:
        """Apply the jointly chosen evidence and current-sport continuity gates."""

        planning_readiness = PlanReadinessService().get_readiness(as_of_date=end_date)
        evidence_start_date = end_date - timedelta(days=PERFORMANCE_HISTORY_DAYS - 1)
        recent_start_date = end_date - timedelta(days=RECENT_SPORT_ACTIVITY_DAYS - 1)
        with session_scope() as session:
            activities = [
                activity
                for activity in get_activities_in_date_range(
                    session,
                    start_date=evidence_start_date,
                    end_date=end_date,
                )
                if activity.sport_type in INCLUDED_SPORT_TYPES
            ]
            evidence_by_activity = get_evidence_for_activities(
                session,
                activity_ids=[activity.id for activity in activities],
            )

        return PerformanceReadiness(
            as_of_date=end_date,
            evidence_start_date=evidence_start_date,
            history=planning_readiness.history,
            planning_blockers=planning_readiness.blockers,
            sports=tuple(
                self._sport_readiness(
                    sport_type=sport_type,
                    activities=activities,
                    evidence_by_activity=evidence_by_activity,
                    recent_start_date=recent_start_date,
                    planning_status=planning_readiness.status,
                    planning_blockers=planning_readiness.blockers,
                )
                for sport_type in INCLUDED_SPORT_TYPES
            ),
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
    def _detailed_activity_fact(
        *,
        activity: Activity,
        detail: ActivityPerformanceDetail,
    ) -> DetailedActivityFact:
        scalar_values, scalar_source = _resolved_scalars(activity, detail)
        return DetailedActivityFact(
            garmin_activity_id=activity.provider_activity_id,
            activity_date=athlete_local_date(activity.start_time),
            sport_type=activity.sport_type,
            split_count=len(detail.splits),
            scalar_source=scalar_source,
            duration_seconds=scalar_values["duration_seconds"],
            distance_meters=scalar_values["distance_meters"],
        )

    @staticmethod
    def _race_evidence_fact(
        *,
        activity: Activity,
        detail: ActivityPerformanceDetail,
        evidence: PerformanceEvidence,
        race: Race,
    ) -> RaceEvidenceFact:
        scalar_values, scalar_source = _resolved_scalars(activity, detail)
        return RaceEvidenceFact(
            garmin_activity_id=activity.provider_activity_id,
            activity_date=athlete_local_date(activity.start_time),
            sport_type=activity.sport_type,
            race_id=race.id,
            race_name=race.name,
            race_date=race.race_date,
            race_distance_meters=race.distance_meters,
            duration_seconds=scalar_values["duration_seconds"],
            distance_meters=scalar_values["distance_meters"],
            average_speed_mps=scalar_values["average_speed_mps"],
            average_heart_rate=scalar_values["average_heart_rate"],
            average_power=scalar_values["average_power"],
            split_count=len(detail.splits),
            scalar_source=scalar_source,
        )

    @staticmethod
    def _benchmark_evidence_fact(
        *,
        activity: Activity,
        detail: ActivityPerformanceDetail,
        evidence: PerformanceEvidence,
    ) -> BenchmarkEvidenceFact:
        scalar_values, scalar_source = _resolved_scalars(activity, detail)
        return BenchmarkEvidenceFact(
            garmin_activity_id=activity.provider_activity_id,
            activity_date=athlete_local_date(activity.start_time),
            sport_type=activity.sport_type,
            protocol=evidence.benchmark_protocol or "unknown",
            duration_seconds=scalar_values["duration_seconds"],
            distance_meters=scalar_values["distance_meters"],
            average_speed_mps=scalar_values["average_speed_mps"],
            average_heart_rate=scalar_values["average_heart_rate"],
            average_power=scalar_values["average_power"],
            split_count=len(detail.splits),
            scalar_source=scalar_source,
        )

    @staticmethod
    def _sport_readiness(
        *,
        sport_type: str,
        activities: list[Activity],
        evidence_by_activity: dict[int, PerformanceEvidence],
        recent_start_date: date,
        planning_status: str,
        planning_blockers,
    ) -> SportPerformanceReadiness:
        sport_activities = [
            activity for activity in activities if activity.sport_type == sport_type
        ]
        evidence_activities = [
            activity
            for activity in sport_activities
            if activity.id in evidence_by_activity
            and evidence_by_activity[activity.id].evidence_type in {"race", "benchmark"}
        ]
        recent_activity_count = sum(
            athlete_local_date(activity.start_time) >= recent_start_date
            for activity in sport_activities
        )
        limitations: list[str] = []
        if planning_blockers:
            limitations.extend(blocker.code for blocker in planning_blockers)
            status = "blocked"
        elif planning_status != "ready":
            limitations.append("planning_history_not_ready")
            status = "insufficient_history"
        elif not evidence_activities:
            limitations.append("no_verified_evidence_in_last_12_weeks")
            status = "general_plan_only"
        elif recent_activity_count < REQUIRED_RECENT_SPORT_ACTIVITIES:
            limitations.append("insufficient_recent_sport_continuity")
            status = "general_plan_only"
        else:
            status = "ready_for_intensity_target"
        return SportPerformanceReadiness(
            sport_type=sport_type,
            status=status,
            verified_evidence_count=len(evidence_activities),
            latest_evidence_date=(
                None
                if not evidence_activities
                else max(athlete_local_date(activity.start_time) for activity in evidence_activities)
            ),
            recent_activity_count=recent_activity_count,
            required_recent_activity_count=REQUIRED_RECENT_SPORT_ACTIVITIES,
            can_propose_intensity_target=status == "ready_for_intensity_target",
            limitations=tuple(limitations),
        )


def _history_limitations(
    coverage: PerformanceDetailCoverage,
    race_evidence: tuple[RaceEvidenceFact, ...],
    benchmark_evidence: tuple[BenchmarkEvidenceFact, ...],
) -> tuple[str, ...]:
    limitations: list[str] = []
    if coverage.eligible_activities == 0:
        limitations.append("no_eligible_run_or_ride_activities_in_last_12_weeks")
    elif coverage.missing_details:
        limitations.append("activity_detail_import_incomplete")
    if not race_evidence and not benchmark_evidence:
        limitations.append("no_verified_performance_evidence")
    limitations.append("performance_target_proposals_belong_to_j3")
    return tuple(limitations)


def _resolved_scalars(
    activity: Activity,
    detail: ActivityPerformanceDetail,
) -> tuple[dict[str, int | float | None], str]:
    """Prefer detail scalars but retain trusted normalized activity facts as fallback."""

    fields = (
        "duration_seconds",
        "distance_meters",
        "average_heart_rate",
        "maximum_heart_rate",
        "average_speed_mps",
        "average_cadence",
        "average_power",
    )
    values: dict[str, int | float | None] = {}
    detail_count = 0
    fallback_value_count = 0
    for field_name in fields:
        detail_value = getattr(detail, field_name)
        if detail_value is not None:
            values[field_name] = detail_value
            detail_count += 1
        else:
            activity_value = getattr(activity, field_name)
            values[field_name] = activity_value
            fallback_value_count += int(activity_value is not None)
    scalar_source = (
        "activity_summary"
        if detail_count == 0
        else "activity_detail" if fallback_value_count == 0 else "mixed"
    )
    return values, scalar_source
