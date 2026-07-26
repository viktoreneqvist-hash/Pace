"""Compose deterministic capacity facts from approved Pace data boundaries."""

from datetime import date

from pace.capacity.analysis import (
    INCLUDED_SPORT_TYPES,
    summarize_continuity,
    summarize_sport_balance,
    summarize_sport_capacity,
)
from pace.capacity.models import CapacityProfile, RecoveryCoverageFact
from pace.database.session import session_scope
from pace.repositories.activity_repository import get_activities_in_date_range
from pace.services.metric_service import MetricService
from pace.services.plan_readiness_service import PlanReadinessService


class CapacityService:
    """Build an auditable capacity profile without targets, advice, or AI calls."""

    def get_profile(self, *, end_date: date) -> CapacityProfile:
        """Return observed facts over the newest contiguous imported history."""

        readiness = PlanReadinessService().get_readiness(as_of_date=end_date)
        history = readiness.history
        if history.covered_start_date is None or history.covered_end_date is None:
            return CapacityProfile(
                as_of_date=end_date,
                status="insufficient_history",
                source_start_date=None,
                source_end_date=None,
                history=history,
                sports=(),
                continuity=None,
                sport_balance=None,
                recovery_coverage=(),
                upcoming_races=readiness.upcoming_races,
                planning_blockers=readiness.blockers,
                limitations=_profile_limitations(readiness.limitations),
            )

        with session_scope() as session:
            activities = get_activities_in_date_range(
                session,
                start_date=history.covered_start_date,
                end_date=history.covered_end_date,
            )
        sports = tuple(
            summarize_sport_capacity(
                activities,
                sport_type=sport_type,
                start_date=history.covered_start_date,
                end_date=history.covered_end_date,
            )
            for sport_type in INCLUDED_SPORT_TYPES
        )
        metrics = MetricService().get_summary(end_date=history.covered_end_date)
        return CapacityProfile(
            as_of_date=end_date,
            status=(
                "blocked"
                if readiness.blockers
                else "ready" if history.is_contiguous else "insufficient_history"
            ),
            source_start_date=history.covered_start_date,
            source_end_date=history.covered_end_date,
            history=history,
            sports=sports,
            continuity=summarize_continuity(
                activities,
                start_date=history.covered_start_date,
                end_date=history.covered_end_date,
            ),
            sport_balance=summarize_sport_balance(sports),
            recovery_coverage=tuple(
                RecoveryCoverageFact(
                    metric=metric.metric,
                    baseline_data_points=metric.baseline_data_points,
                    expected_baseline_days=metric.expected_baseline_days,
                    latest_date=metric.latest_date,
                )
                for metric in metrics.recovery
            ),
            upcoming_races=readiness.upcoming_races,
            planning_blockers=readiness.blockers,
            limitations=_profile_limitations(readiness.limitations),
        )


def _profile_limitations(readiness_limitations: tuple[str, ...]) -> tuple[str, ...]:
    """Keep the J2A profile factual after detailed evidence exists separately."""

    return (*readiness_limitations, "performance_readiness_required_for_j3")
