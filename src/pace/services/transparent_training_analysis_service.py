"""Aggregate inspectable training facts without inventing a load score."""

from datetime import date, timedelta

from pace.database.session import session_scope
from pace.repositories.activity_repository import get_activities_in_date_range
from pace.services.athlete_state_service import AthleteStateService
from pace.services.training_response_trend_service import TrainingResponseTrendService
from pace.timezones import athlete_local_date
from pace.training_analysis.models import (
    SportWindowAnalysis,
    TransparentTrainingAnalysis,
)


ANALYSIS_DAYS = 28


class TransparentTrainingAnalysisService:
    def get_analysis(self, *, end_date: date) -> TransparentTrainingAnalysis:
        start_date = end_date - timedelta(days=ANALYSIS_DAYS - 1)
        with session_scope() as session:
            activities = tuple(
                item
                for item in get_activities_in_date_range(
                    session, start_date=start_date, end_date=end_date
                )
                if item.sport_type in {"run", "ride"}
            )
        sports = tuple(
            _sport_analysis(
                sport_type,
                tuple(item for item in activities if item.sport_type == sport_type),
            )
            for sport_type in ("run", "ride")
        )
        trends = TrainingResponseTrendService().get_trends(end_date=end_date)
        state = AthleteStateService().get_state(end_date=end_date)
        return TransparentTrainingAnalysis(
            start_date=start_date,
            end_date=end_date,
            sports=sports,
            total_duration_hours=sum(item.duration_hours for item in sports),
            total_active_days=len(
                {athlete_local_date(item.start_time) for item in activities}
            ),
            feedback_records=trends.recent.outcomes.feedback_records,
            reported_rpe_average=trends.recent.reported_rpe_average,
            recovery_coverage=tuple(
                (
                    item.metric,
                    item.baseline_data_points,
                    item.expected_baseline_days,
                )
                for item in state.data_quality.recovery
            ),
            limitations=(
                "no_proprietary_training_load_score",
                "missing_feedback_is_unknown",
                "missing_distance_is_not_zero",
            ),
        )


def _sport_analysis(sport_type: str, activities) -> SportWindowAnalysis:
    return SportWindowAnalysis(
        sport_type=sport_type,
        activity_count=len(activities),
        active_days=len({athlete_local_date(item.start_time) for item in activities}),
        duration_hours=sum(item.duration_seconds for item in activities) / 3_600,
        known_distance_km=sum(
            item.distance_meters for item in activities if item.distance_meters is not None
        )
        / 1_000,
        missing_distance_activities=sum(
            item.distance_meters is None for item in activities
        ),
    )
