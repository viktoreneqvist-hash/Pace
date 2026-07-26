"""Coordinate deterministic readable explanations from reviewed rule output."""

from datetime import date

from pace.explanations.hrv import explain_hrv_rules
from pace.explanations.models import ExplanationSummary
from pace.services.rule_service import RuleService


class ExplanationService:
    """Build a concise explanation without new calculations or AI calls."""

    def explain(self, *, end_date: date) -> ExplanationSummary:
        """Explain the approved HRV rules for one reproducible state date."""

        return explain_hrv_rules(RuleService().evaluate(end_date=end_date))
