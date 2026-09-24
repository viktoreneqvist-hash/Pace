from dataclasses import dataclass
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


@dataclass(frozen=True)
class StubPerformanceReadiness:
    status: str = "ready"


def _plan(
    *,
    status="accepted",
    plan_id=9,
    parent_plan_id=8,
    session_date=date(2026, 7, 26),
    sport="run",
) -> TrainingPlanFact:
    return TrainingPlanFact(
        id=plan_id,
        parent_plan_id=parent_plan_id,
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
                scheduled_date=session_date,
                sport_type=sport,
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
    performance_service = type(
        "Performance",
        (),
        {"get_readiness": lambda *_args, **_kwargs: StubPerformanceReadiness()},
    )()
    history_service = type(
        "History",
        (),
        {
            "get_history": lambda *_args, **_kwargs: {
                "recent_detailed_activities": [],
                "daily_history": [],
                "weekly_history": [],
            }
        },
    )()
    historical_plan = _plan(
        status="superseded",
        plan_id=8,
        parent_plan_id=None,
        session_date=date(2026, 7, 24),
        sport="ride",
    )
    plan_history_source = type(
        "Plans",
        (),
        {"list_plans": lambda *_args: (_plan(plan_id=9), historical_plan)},
    )()
    return CoachDialogueService(
        client=StubClient(answer),
        athlete_state_service=state_service,
        rule_service=rule_service,
        explanation_service=explanation_service,
        training_response_trend_service=trend_service,
        performance_service=performance_service,
        training_history_service=history_service,
        plan_history_source=plan_history_source,
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
    assert request.context["training_history"]["weekly_history"] == []
    assert request.context["performance_readiness"]["status"] == "ready"
    history = request.context["plan_lineage"]
    assert history["start_date"] == "2026-06-28"
    assert history["earlier_revisions"][0]["plan_id"] == 8
    assert history["earlier_revisions"][0]["status"] == "superseded"
    session = history["earlier_revisions"][0]["sessions"][0]
    assert session["scheduled_date"] == "2026-07-24"
    assert session["sport_type"] == "ride"
    assert "same_plan" in history["earlier_revisions"][0]["meaning"]
    assert "not separate plans" in history["interpretation"]
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
