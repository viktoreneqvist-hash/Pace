"""Coordinate deterministic Pace rules over one athlete-state snapshot."""

from datetime import date

from pace.rules.hrv import (
    evaluate_hrv_baseline_data_quality,
    evaluate_hrv_context_present,
)
from pace.rules.recovery import (
    evaluate_resting_heart_rate_baseline_data_quality,
    evaluate_resting_heart_rate_elevation,
    evaluate_sleep_duration_baseline_data_quality,
    evaluate_sleep_duration_short_night,
)
from pace.rules.models import RuleEvaluationSummary
from pace.services.athlete_state_service import AthleteStateService
from pace.state.models import AthleteState


class RuleService:
    """Evaluate the reviewed first-slice rules without coaching advice."""

    def evaluate(self, *, end_date: date) -> RuleEvaluationSummary:
        """Evaluate all approved rules against one dynamic athlete state."""

        athlete_state = AthleteStateService().get_state(end_date=end_date)
        return self.evaluate_state(athlete_state)

    def evaluate_state(self, athlete_state: AthleteState) -> RuleEvaluationSummary:
        """Evaluate all approved rules against an already-built athlete state."""

        return RuleEvaluationSummary(
            as_of_date=athlete_state.as_of_date,
            evaluations=(
                evaluate_hrv_baseline_data_quality(athlete_state),
                evaluate_hrv_context_present(athlete_state),
                evaluate_resting_heart_rate_baseline_data_quality(athlete_state),
                evaluate_resting_heart_rate_elevation(athlete_state),
                evaluate_sleep_duration_baseline_data_quality(athlete_state),
                evaluate_sleep_duration_short_night(athlete_state),
            ),
        )
