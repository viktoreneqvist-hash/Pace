"""Compose existing local facts for the read-only Pace dashboard."""

from datetime import date, timedelta

from pace.database.session import session_scope
from pace.presentation.dashboard import write_dashboard_html
from pace.repositories.activity_repository import get_activities_in_date_range
from pace.services.athlete_state_service import AthleteStateService
from pace.services.training_plan_service import TrainingPlanService
from pace.services.training_response_trend_service import TrainingResponseTrendService


class DashboardService:
    def write_dashboard(self, *, end_date: date):
        state = AthleteStateService().get_state(end_date=end_date)
        trends = TrainingResponseTrendService().get_trends(end_date=end_date)
        plans = TrainingPlanService().list_plans()
        plan = next((item for item in plans if item.status == "accepted" and item.block_start_date <= end_date <= item.block_end_date), None)
        with session_scope() as session:
            activities = get_activities_in_date_range(session, start_date=end_date - timedelta(days=27), end_date=end_date)
        return write_dashboard_html(state=state, trends=trends, plan=plan, activities=activities)
