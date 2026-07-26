"""Coordinate one explicit read-only Pace AI question."""

from datetime import date

from pace.ai.client import OpenAIResponsesClient
from pace.ai.context import build_ai_context
from pace.ai.models import PaceAIAnswer, PaceAIRequest
from pace.services.athlete_state_service import AthleteStateService
from pace.services.explanation_service import ExplanationService
from pace.services.rule_service import RuleService
from pace.knowledge.library import load_knowledge_library
from pace.knowledge.selection import select_for_question, serialize_selected_briefs


class PaceAskService:
    """Answer one question over stable Pace facts without database writes."""

    def __init__(
        self,
        *,
        client: OpenAIResponsesClient,
        athlete_state_service: AthleteStateService | None = None,
        rule_service: RuleService | None = None,
        explanation_service: ExplanationService | None = None,
    ) -> None:
        self._client = client
        self._athlete_state_service = athlete_state_service or AthleteStateService()
        self._rule_service = rule_service or RuleService()
        self._explanation_service = explanation_service or ExplanationService()

    def ask(self, *, question: str, end_date: date) -> PaceAIAnswer:
        """Build selected facts locally and send exactly one stateless question."""

        athlete_state = self._athlete_state_service.get_state(end_date=end_date)
        rule_summary = self._rule_service.evaluate_state(athlete_state)
        explanation = self._explanation_service.explain_state(
            athlete_state=athlete_state,
            rule_summary=rule_summary,
        )
        knowledge_library = load_knowledge_library()
        selected_briefs = select_for_question(knowledge_library, question=question)
        return self._client.answer(
            PaceAIRequest(
                question=question,
                context=build_ai_context(
                    athlete_state=athlete_state,
                    rule_summary=rule_summary,
                    explanation=explanation,
                    knowledge_briefs=serialize_selected_briefs(
                        knowledge_library, briefs=selected_briefs
                    ),
                ),
            )
        )
