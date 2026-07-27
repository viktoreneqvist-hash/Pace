"""Compose bounded local facts for one explicit weekly AI review."""

from dataclasses import asdict
from datetime import date

from pace.ai.context import build_ai_context
from pace.knowledge.library import load_knowledge_library
from pace.knowledge.selection import select_for_tags, serialize_selected_briefs
from pace.presentation.weekly_review import write_weekly_review_html
from pace.services.athlete_state_service import AthleteStateService
from pace.services.explanation_service import ExplanationService
from pace.services.personalization_evidence_service import PersonalizationEvidenceService
from pace.services.rule_service import RuleService
from pace.services.training_response_trend_service import TrainingResponseTrendService
from pace.weekly_review.client import WeeklyReviewClient
from pace.weekly_review.models import WeeklyReviewRequest


class WeeklyReviewService:
    def __init__(self, *, client: WeeklyReviewClient) -> None:
        self._client = client

    def create(self, *, end_date: date):
        state = AthleteStateService().get_state(end_date=end_date)
        rules = RuleService().evaluate_state(state)
        explanation = ExplanationService().explain_state(athlete_state=state, rule_summary=rules)
        library = load_knowledge_library()
        context = build_ai_context(athlete_state=state, rule_summary=rules, explanation=explanation, knowledge_briefs=serialize_selected_briefs(library, briefs=select_for_tags(library, tags={"progression", "intensity", "recovery", "run_ride"})))
        context["training_response_trends"] = asdict(TrainingResponseTrendService().get_trends(end_date=end_date))
        context["personalization_evidence"] = asdict(PersonalizationEvidenceService().get_evidence(end_date=end_date))
        answer = self._client.review(WeeklyReviewRequest(context=context))
        return write_weekly_review_html(end_date=end_date, answer=answer)
