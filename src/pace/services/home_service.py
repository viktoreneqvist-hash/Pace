"""Compose existing read-only services into one local Pace Home report."""

from datetime import date

from pace.presentation.home import write_home_html
from pace.presentation.plan_views import write_plan_html_report
from pace.services.dashboard_service import DashboardService
from pace.services.heart_rate_zone_service import HeartRateZoneService
from pace.services.personalization_evidence_service import PersonalizationEvidenceService
from pace.services.plan_checkpoint_service import PlanCheckpointService
from pace.services.race_service import RaceService
from pace.services.training_plan_service import TrainingPlanService
from pace.services.training_preference_service import TrainingPreferenceService


class HomeService:
    def write_home(self, *, end_date: date):
        plans = TrainingPlanService().list_plans()
        plan = next(
            (
                item
                for item in plans
                if item.status == "accepted"
                and item.block_start_date <= end_date <= item.block_end_date
            ),
            None,
        )
        checkpoint = PlanCheckpointService().get_checkpoint(as_of_date=end_date)
        personalization = PersonalizationEvidenceService().get_evidence(
            end_date=end_date
        )
        races = RaceService().list_upcoming_races(as_of_date=end_date)
        preference = TrainingPreferenceService().get_preference()
        ride_zone_profile = HeartRateZoneService().get_profile(sport_type="ride")
        DashboardService().write_dashboard(end_date=end_date)
        if plan is not None:
            write_plan_html_report(plan)
        return write_home_html(
            checkpoint=checkpoint,
            plan=plan,
            personalization=personalization,
            races=races,
            preference=preference,
            ride_zone_profile=ride_zone_profile,
        )
