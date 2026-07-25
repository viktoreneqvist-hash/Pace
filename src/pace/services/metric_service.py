"""Application service that reads Pace facts and returns deterministic metrics."""

from datetime import date, timedelta

from pace.analysis.models import PaceMetricSummary
from pace.analysis.recovery_metrics import BASELINE_DAYS, summarize_recovery
from pace.analysis.training_metrics import WEEK_DAYS, summarize_weekly_training
from pace.database.session import session_scope
from pace.repositories.activity_repository import get_activities_in_date_range
from pace.repositories.daily_metric_repository import get_daily_metrics_in_date_range


class MetricService:
    """Coordinate read-only database queries with pure analysis functions."""

    def get_summary(self, *, end_date: date) -> PaceMetricSummary:
        """Return Pace's initial factual training and recovery summary."""

        activity_start_date = end_date - timedelta(days=WEEK_DAYS * 2 - 1)
        recovery_start_date = end_date - timedelta(days=BASELINE_DAYS - 1)

        with session_scope() as session:
            activities = get_activities_in_date_range(
                session,
                start_date=activity_start_date,
                end_date=end_date,
            )
            daily_metrics = get_daily_metrics_in_date_range(
                session,
                start_date=recovery_start_date,
                end_date=end_date,
            )

        return PaceMetricSummary(
            end_date=end_date,
            training=summarize_weekly_training(activities, end_date=end_date),
            recovery=summarize_recovery(daily_metrics, end_date=end_date),
        )
