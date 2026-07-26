"""Coordinate deterministic readable explanations from reviewed rule output."""

from datetime import date

from pace.explanations.hrv import explain_hrv_rules
from pace.explanations.recovery import (
    explain_garmin_current_facts,
    explain_recovery_rules,
)
from pace.explanations.models import ExplanationSummary
from pace.services.athlete_state_service import AthleteStateService
from pace.services.rule_service import RuleService


class ExplanationService:
    """Build a concise explanation without new calculations or AI calls."""

    def explain(self, *, end_date: date) -> ExplanationSummary:
        """Explain the approved HRV rules for one reproducible state date."""

        athlete_state = AthleteStateService().get_state(end_date=end_date)
        rule_summary = RuleService().evaluate_state(athlete_state)
        hrv_explanation = explain_hrv_rules(rule_summary)
        return ExplanationSummary(
            as_of_date=athlete_state.as_of_date,
            items=(
                *hrv_explanation.items,
                *explain_recovery_rules(rule_summary),
                *explain_garmin_current_facts(athlete_state.garmin_current_facts),
            ),
            context_check_in=hrv_explanation.context_check_in,
        )
