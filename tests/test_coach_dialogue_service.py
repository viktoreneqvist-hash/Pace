from datetime import date

import pytest

from pace.coach.models import CoachDialogueAnswer, PlanAdjustmentDraft
from pace.planning.draft_models import PlannedSessionDraft, SessionTargetDraft
from pace.planning.plan_models import (
    CoachAssessmentFact,
    PlanSessionFact,
    SessionTargetFact,
    TrainingPlanFact,
)
from pace.services import coach_dialogue_service
from pace.services.coach_dialogue_service import CoachDialogueService
from pace.trends.models import FeedbackWindowSummary, OutcomeSummary, TrainingResponseTrends


class StubClient:
    def __init__(self, answer) -> None:
        self.answer_value = answer
        self.request = None

    def answer(self, request):
        self.request = request
        return self.answer_value


def _plan(*, status="accepted") -> TrainingPlanFact:
    return TrainingPlanFact(
        id=9,
        parent_plan_id=None,
        status=status,
        contract_version=2,
        goal_mode="general",
        race_id=None,
        as_of_date=date(2026, 7, 26),
        block_start_date=date(2026, 7, 26),
        block_end_date=date(2026, 8, 22),
        detailed_start_date=date(2026, 7, 26),
        detailed_end_date=date(2026, 8, 8),
        block_outline=(),
        sessions=(
            PlanSessionFact(
                id=4,
                scheduled_date=date(2026, 7, 26),
                sport_type="run",
                purpose="Planerat pass.",
                distance_meters=5_000,
                duration_seconds=1_800,
                heart_rate_zone=None,
                target=SessionTargetFact("rpe", 2, 3, None, None, None),
                target_display="RPE 2–3",
                feedback_outcome=None,
            ),
        ),
        coach_assessment=CoachAssessmentFact((), (), (), "", (), ()),
    )


def _answer(adjustment) -> CoachDialogueAnswer:
    return CoachDialogueAnswer(
        answer="Gör så.",
        observations=("Fakta.",),
        uncertainties=("Begränsning.",),
        knowledge_references=(),
        adjustment_draft=adjustment,
    )


def _service(monkeypatch, answer):
    monkeypatch.setattr(
        coach_dialogue_service,
        "build_ai_context",
        lambda **_kwargs: {"schema_version": 2},
    )
    state_service = type("State", (), {"get_state": lambda *_args, **_kwargs: object()})()
    rule_service = type("Rules", (), {"evaluate_state": lambda *_args, **_kwargs: object()})()
    explanation_service = type("Explain", (), {"explain_state": lambda *_args, **_kwargs: object()})()
    trends = TrainingResponseTrends(
        as_of_date=date(2026, 7, 26),
        status="ready",
        recent=FeedbackWindowSummary(date(2026, 6, 29), date(2026, 7, 26), OutcomeSummary(6, 5, 1, 0, 83.3), 5.0, 2, (), ()),
        previous=FeedbackWindowSummary(date(2026, 6, 1), date(2026, 6, 28), OutcomeSummary(4, 4, 0, 0, 100.0), None, 0, (), ()),
        recent_required_feedback_records=6,
        previous_required_feedback_records=4,
        comparison_available=True,
        limitations=("explicit_feedback_only",),
    )
    trend_service = type("Trends", (), {"get_trends": lambda *_args, **_kwargs: trends})()
    return CoachDialogueService(
        client=StubClient(answer),
        athlete_state_service=state_service,
        rule_service=rule_service,
        explanation_service=explanation_service,
        training_response_trend_service=trend_service,
    )


def test_dialogue_sends_only_an_active_accepted_plan_and_keeps_history_bounded(monkeypatch):
    service = _service(
        monkeypatch,
        _answer(PlanAdjustmentDraft("skip", 4, "Skippa i dag.", None)),
    )

    answer = service.ask(
        question="Kan jag vila?",
        plan=_plan(),
        end_date=date(2026, 7, 26),
        conversation=tuple(
            {"role": "athlete", "text": f"fråga {index}"} for index in range(10)
        ),
    )

    assert answer.adjustment_draft is not None
    request = service._client.request
    assert request.context["active_plan"]["id"] == 9
    assert request.context["training_response_trends"]["status"] == "ready"
    assert len(request.conversation) == 8
    assert request.conversation[0]["text"] == "fråga 2"


def test_dialogue_rejects_adjustments_for_a_different_day(monkeypatch):
    replacement = PlannedSessionDraft(
        scheduled_date=date(2026, 7, 27),
        sport_type="run",
        purpose="Fel dag.",
        distance_meters=5_000,
        duration_seconds=1_800,
        heart_rate_zone=None,
        target=SessionTargetDraft("rpe", 2, 3, None, None, None),
    )
    service = _service(
        monkeypatch,
        _answer(PlanAdjustmentDraft("replace", 4, "Byt.", replacement)),
    )

    with pytest.raises(ValueError, match="selected date"):
        service.ask(
            question="Byt?", plan=_plan(), end_date=date(2026, 7, 26)
        )


def test_dialogue_requires_an_accepted_plan(monkeypatch):
    service = _service(monkeypatch, _answer(None))

    with pytest.raises(ValueError, match="accepted plan"):
        service.ask(question="Test", plan=_plan(status="draft"), end_date=date(2026, 7, 26))
