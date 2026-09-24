"""Build bounded plan-aware coach-dialogue requests without writing a plan."""

from dataclasses import asdict
from datetime import date, timedelta
from typing import Protocol

from pace.ai.context import build_ai_context, serialize_pace_facts
from pace.coach.models import CoachDialogueAnswer, CoachDialogueRequest
from pace.knowledge.library import load_knowledge_library
from pace.knowledge.selection import (
    select_for_plan_context,
    select_for_question,
    serialize_selected_briefs,
)
from pace.planning.draft_models import PlannedSessionDraft
from pace.planning.plan_models import TrainingPlanFact
from pace.services.athlete_state_service import AthleteStateService
from pace.services.explanation_service import ExplanationService
from pace.services.performance_history_service import PerformanceHistoryService
from pace.services.rule_service import RuleService
from pace.services.training_plan_service import (
    WEEKDAY_CODES,
    TrainingPlanService,
    _validate_heart_rate_zone,
    _validate_session_target,
)
from pace.services.training_preference_service import TrainingPreferenceService
from pace.services.training_response_trend_service import TrainingResponseTrendService
from pace.services.coaching_principle_service import CoachingPrincipleService
from pace.services.coach_training_history_service import CoachTrainingHistoryService
from pace.services.personalization_evidence_service import PersonalizationEvidenceService


MAX_DIALOGUE_MESSAGES = 8
PLAN_HISTORY_PAST_DAYS = 28
PLAN_HISTORY_FUTURE_DAYS = 14
MAX_PLAN_HISTORY_VERSIONS = 6


class CoachDialogueClient(Protocol):
    def answer(self, request: CoachDialogueRequest) -> CoachDialogueAnswer: ...


class PlanHistorySource(Protocol):
    def list_plans(self) -> tuple[TrainingPlanFact, ...]: ...


class CoachDialogueService:
    """Coordinate a non-persistent coach discussion over one accepted plan."""

    def __init__(
        self,
        *,
        client: CoachDialogueClient,
        athlete_state_service: AthleteStateService | None = None,
        rule_service: RuleService | None = None,
        explanation_service: ExplanationService | None = None,
        performance_service: PerformanceHistoryService | None = None,
        training_history_service: CoachTrainingHistoryService | None = None,
        preference_service: TrainingPreferenceService | None = None,
        training_response_trend_service: TrainingResponseTrendService | None = None,
        plan_history_source: PlanHistorySource | None = None,
    ) -> None:
        self._client = client
        self._athlete_state_service = athlete_state_service or AthleteStateService()
        self._rule_service = rule_service or RuleService()
        self._explanation_service = explanation_service or ExplanationService()
        self._performance_service = performance_service or PerformanceHistoryService()
        self._training_history_service = (
            training_history_service or CoachTrainingHistoryService()
        )
        self._preference_service = preference_service or TrainingPreferenceService()
        self._training_response_trend_service = (
            training_response_trend_service or TrainingResponseTrendService()
        )
        self._plan_history_source = plan_history_source or TrainingPlanService()

    def ask(
        self,
        *,
        question: str,
        plan: TrainingPlanFact,
        end_date: date,
        conversation: tuple[dict[str, str], ...] = (),
    ) -> CoachDialogueAnswer:
        """Answer one question and validate any unsaved same-day adjustment."""

        if plan.status != "accepted":
            raise ValueError("Coachdialog requires an accepted plan.")
        if not plan.block_start_date <= end_date <= plan.block_end_date:
            raise ValueError("The accepted plan is not active on the selected date.")
        clean_question = question.strip()
        if not clean_question:
            raise ValueError("Coach question cannot be empty.")
        athlete_state = self._athlete_state_service.get_state(end_date=end_date)
        rule_summary = self._rule_service.evaluate_state(athlete_state)
        explanation = self._explanation_service.explain_state(
            athlete_state=athlete_state,
            rule_summary=rule_summary,
        )
        library = load_knowledge_library()
        knowledge_briefs = _selected_knowledge(
            library=library,
            question=clean_question,
            plan=plan,
        )
        context = build_ai_context(
            athlete_state=athlete_state,
            rule_summary=rule_summary,
            explanation=explanation,
            knowledge_briefs=knowledge_briefs,
        )
        context["active_plan"] = _serialize_active_plan(plan)
        context["plan_lineage"] = _serialize_plan_lineage(
            plans=self._plan_history_source.list_plans(),
            active_plan=plan,
            end_date=end_date,
        )
        context["training_response_trends"] = asdict(
            self._training_response_trend_service.get_trends(end_date=end_date)
        )
        context["athlete_confirmed_coach_principles"] = [
            {"id": item.id, "statement": item.statement, "source_plan_id": item.source_plan_id}
            for item, review_due in CoachingPrincipleService().list_active(as_of_date=end_date)
            if not review_due
        ]
        context["personalization_evidence"] = asdict(PersonalizationEvidenceService().get_evidence(end_date=end_date))
        context["training_history"] = self._training_history_service.get_history(
            end_date=end_date
        )
        context["performance_readiness"] = serialize_pace_facts(
            asdict(self._performance_service.get_readiness(end_date=end_date))
        )
        preference = self._preference_service.get_preference()
        if preference is not None:
            context["athlete_preferences"] = {
                "sport_role": preference.sport_role,
                "coaching_ambition": getattr(
                    preference, "coaching_ambition", "balanced"
                ),
            }
        answer = self._client.answer(
            CoachDialogueRequest(
                question=clean_question,
                context=context,
                conversation=_bounded_conversation(conversation),
            )
        )
        if answer.adjustment_draft is not None:
            self._validate_adjustment(
                plan=plan,
                end_date=end_date,
                adjustment=answer.adjustment_draft,
            )
        if answer.feedback_draft is not None:
            self._validate_feedback_draft(plan=plan, feedback=answer.feedback_draft)
        return answer

    def _validate_feedback_draft(self, *, plan, feedback) -> None:
        if not any(session.id == feedback.planned_session_id for session in plan.sessions):
            raise ValueError("Coach feedback draft referenced a session outside the active plan.")

    def _validate_adjustment(self, *, plan, end_date, adjustment) -> None:
        if adjustment.action == "keep_plan":
            return
        replaced = next(
            (session for session in plan.sessions if session.id == adjustment.replaces_session_id),
            None,
        )
        if replaced is None:
            raise ValueError("Coach adjustment referenced a session outside the active plan.")
        if replaced.scheduled_date != end_date:
            raise ValueError("Coach adjustment may only reference a session on the selected date.")
        if adjustment.action == "skip":
            return
        replacement = adjustment.proposed_session
        if replacement is None:
            raise ValueError("Coach replacement adjustment is missing its proposed session.")
        self._validate_replacement_session(session=replacement, end_date=end_date)

    def _validate_replacement_session(
        self,
        *,
        session: PlannedSessionDraft,
        end_date: date,
    ) -> None:
        if session.scheduled_date != end_date:
            raise ValueError("Coach replacement must stay on the selected date.")
        if session.sport_type not in {"run", "ride"}:
            raise ValueError("Coach replacement used an unsupported sport.")
        preference = self._preference_service.get_preference()
        if preference is not None and (
            (preference.sport_role == "run_only" and session.sport_type != "run")
            or (preference.sport_role == "ride_only" and session.sport_type != "ride")
        ):
            raise ValueError("Coach replacement used a sport outside the athlete's selected sport mode.")
        if session.distance_meters is None and session.duration_seconds is None:
            raise ValueError("Coach replacement needs distance or duration.")
        if session.sport_type == "ride" and (
            session.distance_meters is None
            or session.duration_seconds is None
            or session.heart_rate_zone not in {1, 2, 3, 4, 5}
        ):
            raise ValueError("Coach cycling replacement needs distance, duration, and Garmin zone.")
        if session.sport_type == "run" and session.heart_rate_zone is not None:
            raise ValueError("Coach running replacement cannot use a cycling heart-rate zone.")
        performance = self._performance_service.get_readiness(end_date=end_date)
        allowed_intensity = {
            sport.sport_type: set(sport.allowed_intensity_types)
            for sport in performance.sports
        }
        _validate_session_target(
            session=session,
            allowed_intensity_types=allowed_intensity.get(session.sport_type, set()),
            performance_readiness=performance,
        )
        _validate_heart_rate_zone(session=session, performance_readiness=performance)
        self._validate_availability(session=session)

    def _validate_availability(self, *, session: PlannedSessionDraft) -> None:
        preference = self._preference_service.get_preference()
        if preference is None:
            raise ValueError("Coach adjustment requires saved training preferences.")
        weekday = WEEKDAY_CODES[session.scheduled_date.weekday()]
        available = next(
            (item for item in preference.available_days if item["day"] == weekday), None
        )
        if available is None:
            raise ValueError("Coach replacement is outside athlete availability.")
        minutes = available["minutes"]
        if minutes is not None and (
            session.duration_seconds is None or session.duration_seconds > minutes * 60
        ):
            raise ValueError("Coach replacement exceeds athlete availability.")


def _selected_knowledge(*, library, question: str, plan: TrainingPlanFact) -> dict[str, object]:
    plan_context = {
        "fact_catalog": {
            "goal": {"value": {"race": {} if plan.goal_mode == "race" else None}},
            "capacity_profile": {
                "value": {
                    "sports": [
                        {"sport_type": sport}
                        for sport in sorted({session.sport_type for session in plan.sessions})
                    ]
                }
            },
        }
    }
    selected = (*select_for_plan_context(library, context=plan_context), *select_for_question(library, question=question))
    unique = tuple({brief.id: brief for brief in selected}.values())[:3]
    return serialize_selected_briefs(library, briefs=unique)


def _serialize_active_plan(plan: TrainingPlanFact) -> dict[str, object]:
    return {
        "id": plan.id,
        "status": plan.status,
        "block_start_date": plan.block_start_date.isoformat(),
        "block_end_date": plan.block_end_date.isoformat(),
        "detailed_start_date": plan.detailed_start_date.isoformat(),
        "detailed_end_date": plan.detailed_end_date.isoformat(),
        "sessions": [
            {
                "id": session.id,
                "scheduled_date": session.scheduled_date.isoformat(),
                "sport_type": session.sport_type,
                "purpose": session.purpose,
                "distance_meters": session.distance_meters,
                "duration_seconds": session.duration_seconds,
                "heart_rate_zone": session.heart_rate_zone,
                "target": asdict(session.target),
                "target_display": session.target_display,
                "feedback_outcome": session.feedback_outcome,
            }
            for session in plan.sessions
        ],
    }


def _serialize_plan_lineage(
    *,
    plans: tuple[TrainingPlanFact, ...],
    active_plan: TrainingPlanFact,
    end_date: date,
) -> dict[str, object]:
    """Expose bounded revisions of the same logical plan, never unrelated plans."""

    start_date = end_date - timedelta(days=PLAN_HISTORY_PAST_DAYS)
    history_end_date = end_date + timedelta(days=PLAN_HISTORY_FUTURE_DAYS)
    plans_by_id = {plan.id: plan for plan in plans}
    lineage: list[TrainingPlanFact] = []
    parent_id = active_plan.parent_plan_id
    while parent_id is not None and len(lineage) < MAX_PLAN_HISTORY_VERSIONS:
        parent = plans_by_id.get(parent_id)
        if parent is None:
            break
        lineage.append(parent)
        parent_id = parent.parent_plan_id

    versions: list[dict[str, object]] = []
    for plan in lineage:
        sessions = [
            session
            for session in plan.sessions
            if start_date <= session.scheduled_date <= history_end_date
        ]
        if not sessions:
            continue
        versions.append(
            {
                "plan_id": plan.id,
                "parent_plan_id": plan.parent_plan_id,
                "status": plan.status,
                "meaning": "earlier_revision_of_the_same_plan_not_proof_of_completion",
                "detailed_start_date": plan.detailed_start_date.isoformat(),
                "detailed_end_date": plan.detailed_end_date.isoformat(),
                "sessions": [
                    {
                        "session_id": session.id,
                        "scheduled_date": session.scheduled_date.isoformat(),
                        "sport_type": session.sport_type,
                        "purpose": session.purpose,
                        "distance_meters": session.distance_meters,
                        "duration_seconds": session.duration_seconds,
                        "target_display": session.target_display,
                        "feedback_outcome": session.feedback_outcome,
                    }
                    for session in sessions
                ],
            }
        )
    return {
        "active_plan_id": active_plan.id,
        "start_date": start_date.isoformat(),
        "end_date": history_end_date.isoformat(),
        "earlier_revisions": versions,
        "interpretation": (
            "These are earlier revisions of the same logical training plan, not separate "
            "plans. A session omitted by the active revision is not proof of an intentional "
            "cancellation because Pace has no explicit cancellation fact. State the revision "
            "conflict instead of calling the date a rest day. Earlier prescriptions do not "
            "prove completion; use Garmin activity facts or athlete feedback for that."
        ),
    }


def _bounded_conversation(conversation: tuple[dict[str, str], ...]) -> tuple[dict[str, str], ...]:
    valid = tuple(
        item
        for item in conversation
        if set(item) == {"role", "text"}
        and item["role"] in {"athlete", "coach"}
        and bool(item["text"].strip())
    )
    return valid[-MAX_DIALOGUE_MESSAGES:]
