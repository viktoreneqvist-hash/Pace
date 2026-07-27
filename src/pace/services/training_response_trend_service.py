"""Service boundary for local, structured feedback trends."""

from datetime import date, timedelta

from pace.database.session import session_scope
from pace.repositories.training_plan_repository import list_feedback_trend_records
from pace.trends.analysis import build_training_response_trends
from pace.trends.models import TrainingResponseTrends


class TrainingResponseTrendService:
    """Read only explicit feedback in two bounded 28-day windows."""

    def get_trends(self, *, end_date: date) -> TrainingResponseTrends:
        with session_scope() as session:
            records = list_feedback_trend_records(
                session,
                start_date=end_date - timedelta(days=55),
                end_date=end_date,
            )
        return build_training_response_trends(as_of_date=end_date, records=records)
