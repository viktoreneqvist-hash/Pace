"""Generate, validate, version, and revise explicit Pace plan versions."""

from dataclasses import asdict
from datetime import date, timedelta
import json
from typing import Callable, Protocol

from pace.database.models import PlannedSession, TrainingPlan
from pace.database.session import session_scope
from pace.performance.models import PerformanceReadiness
from pace.planning.draft_models import (
    GeneratedPlanDraft,
    PlanGenerationRequest,
    SessionTargetDraft,
    WorkoutStepDraft,
)
from pace.planning.plan_models import (
    CoachAssessmentFact,
    PlanSessionFact,
    SessionTargetFact,
    TrainingPlanFact,
    VolumeBoundaryBreachFact,
    VolumeExceptionFact,
    WeeklyVolumeExceptionFact,
    WorkoutStepFact,
)
from pace.repositories.context_event_repository import get_context_events_in_date_range
from pace.repositories.race_repository import get_race_by_id
from pace.repositories.training_plan_repository import (
    create_planned_session,
    create_training_plan,
    get_feedback_for_sessions,
    get_planned_session,
    get_sessions_for_plan,
    get_training_plan,
    list_training_plans,
    upsert_session_feedback,
)
from pace.services.capacity_service import CapacityService
from pace.services.coach_training_history_service import (
    CoachTrainingHistoryService,
    build_planning_continuity_facts,
)
from pace.services.plan_readiness_service import PlanReadinessService
from pace.services.performance_history_service import PerformanceHistoryService
from pace.services.race_service import resolved_taper
from pace.services.training_preference_service import TrainingPreferenceService
from pace.services.training_response_trend_service import TrainingResponseTrendService
from pace.services.coaching_principle_service import CoachingPrincipleService
from pace.services.personalization_evidence_service import (
    PersonalizationEvidenceService,
)
from pace.knowledge.library import load_knowledge_library
from pace.knowledge.selection import select_for_plan_context, serialize_selected_briefs


SUPPORTED_PLAN_DAYS = frozenset({7, 14})
SUPPORTED_FEEDBACK_OUTCOMES = frozenset({"completed", "completed_limited", "skipped"})
SUPPORTED_FEEDBACK_REASON_CODES = frozenset(
    {"schedule", "fatigue", "pain", "illness", "travel", "other"}
)
WEEKDAY_CODES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
CURRENT_PLAN_CONTRACT_VERSION = 3


class PlanDraftGenerator(Protocol):
    def generate(self, request: PlanGenerationRequest) -> GeneratedPlanDraft: ...


class TrainingPlanService:
    """Keep AI draft generation behind deterministic local planning boundaries."""

    def __init__(
        self,
        *,
        generator: PlanDraftGenerator | None = None,
        plan_readiness_service: PlanReadinessService | None = None,
        capacity_service: CapacityService | None = None,
        performance_service: PerformanceHistoryService | None = None,
        preference_service: TrainingPreferenceService | None = None,
        training_response_trend_service: TrainingResponseTrendService | None = None,
        training_history_service: CoachTrainingHistoryService | None = None,
    ) -> None:
        self._generator = generator
        self._plan_readiness_service = plan_readiness_service or PlanReadinessService()
        self._capacity_service = capacity_service or CapacityService()
        self._performance_service = performance_service or PerformanceHistoryService()
        self._preference_service = preference_service or TrainingPreferenceService()
        self._training_response_trend_service = (
            training_response_trend_service or TrainingResponseTrendService()
        )
        self._training_history_service = (
            training_history_service or CoachTrainingHistoryService()
        )

    def generate_draft(
        self,
        *,
        as_of_date: date,
        detailed_days: int,
        race_id: int | None,
    ) -> TrainingPlanFact:
        """Generate and activate a validated plan after the athlete's explicit click."""

        goal = self._resolve_goal(as_of_date=as_of_date, race_id=race_id)
        detailed_start_date = as_of_date
        detailed_end_date = min(
            detailed_start_date
            + timedelta(days=_validate_plan_days(detailed_days) - 1),
            goal["block_end_date"],
        )
        context = self._build_context(
            as_of_date=as_of_date,
            goal=goal,
            detailed_start_date=detailed_start_date,
            detailed_end_date=detailed_end_date,
            feedback=(),
            parent_plan=None,
        )
        performance_readiness = self._performance_service.get_readiness(
            end_date=as_of_date
        )
        generated = self._generate_validated(
            request=PlanGenerationRequest(mode="initial_draft", context=context),
            validate=lambda candidate: self._validate_generated_plan(
                generated=candidate,
                detailed_start_date=detailed_start_date,
                detailed_end_date=detailed_end_date,
                block_start_date=goal["block_start_date"],
                block_end_date=goal["block_end_date"],
                performance_readiness=performance_readiness,
                context=context,
            ),
        )
        volume_exception = _volume_exception_for_generated(
            generated=generated, context=context
        )
        return self._persist_plan(
            parent_plan_id=None,
            goal=goal,
            as_of_date=as_of_date,
            detailed_start_date=detailed_start_date,
            detailed_end_date=detailed_end_date,
            generated=generated,
            context=context,
            performance_readiness=performance_readiness,
            volume_exception=volume_exception,
        )

    def generate_revision(
        self,
        *,
        plan_id: int,
        as_of_date: date,
        detailed_days: int,
    ) -> TrainingPlanFact:
        """Create and activate a separate short-horizon revision; never edit its parent."""

        with session_scope() as session:
            parent = get_training_plan(session, plan_id=plan_id)
            if parent is None:
                raise ValueError(f"No plan exists with id {plan_id}.")
            if parent.status != "accepted":
                raise ValueError("Only an accepted plan can receive a revision draft.")
            if parent.contract_version != CURRENT_PLAN_CONTRACT_VERSION:
                raise ValueError(
                    "Legacy plans must be regenerated before they can be revised."
                )
            if not _has_complete_assessment(parent.coach_assessment):
                raise ValueError(
                    "Plans without a complete coach assessment cannot be revised."
                )
            sessions = get_sessions_for_plan(session, plan_id=parent.id)
            feedback_by_session = get_feedback_for_sessions(
                session, session_ids=[item.id for item in sessions]
            )
        if as_of_date > parent.block_end_date:
            raise ValueError(
                "The accepted plan's block has ended; create a new plan draft."
            )
        goal = _goal_from_parent(parent)
        detailed_start_date = as_of_date
        detailed_end_date = min(
            detailed_start_date
            + timedelta(days=_validate_plan_days(detailed_days) - 1),
            parent.block_end_date,
        )
        feedback = tuple(
            {
                "session_id": item.id,
                "scheduled_date": item.scheduled_date.isoformat(),
                "outcome": feedback_by_session[item.id].outcome,
                "perceived_exertion": feedback_by_session[item.id].perceived_exertion,
                "reason_code": feedback_by_session[item.id].reason_code,
                "workout_steps": _serialize_stored_workout_steps(item),
                "note": (
                    feedback_by_session[item.id].note
                    if feedback_by_session[item.id].share_note_with_ai
                    else None
                ),
            }
            for item in sessions
            if item.id in feedback_by_session
        )
        context = self._build_context(
            as_of_date=as_of_date,
            goal=goal,
            detailed_start_date=detailed_start_date,
            detailed_end_date=detailed_end_date,
            feedback=feedback,
            parent_plan=_parent_plan_context(
                parent=parent,
                sessions=sessions,
                feedback_by_session=feedback_by_session,
            ),
        )
        # The accepted parent owns its block outline. A revision may only
        # replace the short detailed window, never silently redefine the block.
        parent_outline = tuple(
            _deserialize_outline_item(item) for item in parent.block_outline
        )
        performance_readiness = self._performance_service.get_readiness(
            end_date=as_of_date
        )

        def validate_revision(candidate: GeneratedPlanDraft) -> None:
            self._validate_generated_plan(
                generated=GeneratedPlanDraft(
                    block_outline=parent_outline,
                    sessions=candidate.sessions,
                    coach_assessment=candidate.coach_assessment,
                ),
                detailed_start_date=detailed_start_date,
                detailed_end_date=detailed_end_date,
                block_start_date=goal["block_start_date"],
                block_end_date=goal["block_end_date"],
                performance_readiness=performance_readiness,
                context=context,
            )

        candidate = self._generate_validated(
            request=PlanGenerationRequest(mode="revision_draft", context=context),
            validate=validate_revision,
        )
        generated = GeneratedPlanDraft(
            block_outline=parent_outline,
            sessions=candidate.sessions,
            coach_assessment=candidate.coach_assessment,
        )
        volume_exception = _volume_exception_for_generated(
            generated=generated, context=context
        )
        return self._persist_plan(
            parent_plan_id=parent.id,
            goal=goal,
            as_of_date=as_of_date,
            detailed_start_date=detailed_start_date,
            detailed_end_date=detailed_end_date,
            generated=generated,
            context=context,
            performance_readiness=performance_readiness,
            volume_exception=volume_exception,
        )

    def approve_volume_exception(self, *, plan_id: int) -> TrainingPlanFact:
        """Activate one race-specific exception after explicit athlete approval."""

        with session_scope() as session:
            plan = get_training_plan(session, plan_id=plan_id)
            if plan is None:
                raise ValueError(f"No plan exists with id {plan_id}.")
            if plan.status != "volume_exception_pending":
                raise ValueError("This plan has no pending race-volume exception.")
            if plan.race_id is None:
                raise ValueError(
                    "Only a race-directed plan can use a volume exception."
                )
            race = get_race_by_id(session, plan.race_id)
            if race is None or race.status != "active":
                raise ValueError("The target race is no longer active.")
            volume_exception = _stored_volume_exception(plan.context_snapshot)
            if volume_exception is None or not volume_exception.weeks:
                raise ValueError(
                    "The pending plan has no valid volume-exception record."
                )
            if plan.parent_plan_id is not None:
                parent = get_training_plan(session, plan_id=plan.parent_plan_id)
                if parent is None or parent.status != "accepted":
                    raise ValueError(
                        "This revision is stale because its parent is no longer active."
                    )
            context_snapshot = dict(plan.context_snapshot)
            serialized_exception = dict(context_snapshot["volume_exception"])
            serialized_exception["approved"] = True
            context_snapshot["volume_exception"] = serialized_exception
            plan.context_snapshot = context_snapshot
            plan.status = "accepted"
            _supersede_replaced_active_plans(
                session=session,
                plan=plan,
                as_of_date=plan.as_of_date,
            )
            session.flush()
            return _plan_fact(session, plan)

    def accept_plan(self, *, plan_id: int) -> TrainingPlanFact:
        with session_scope() as session:
            plan = get_training_plan(session, plan_id=plan_id)
            if plan is None:
                raise ValueError(f"No plan exists with id {plan_id}.")
            if plan.status == "accepted":
                return _plan_fact(session, plan)
            if plan.status != "draft":
                raise ValueError("Only a draft plan can be accepted.")
            if plan.contract_version != CURRENT_PLAN_CONTRACT_VERSION:
                raise ValueError(
                    "Legacy draft plans must be regenerated before acceptance."
                )
            if plan.race_id is not None:
                race = get_race_by_id(session, plan.race_id)
                if race is None or race.status != "active":
                    raise ValueError("A draft for a cancelled race cannot be accepted.")
            if not _has_complete_assessment(plan.coach_assessment):
                raise ValueError(
                    "A complete coach assessment is required before acceptance."
                )
            if plan.parent_plan_id is not None:
                parent = get_training_plan(session, plan_id=plan.parent_plan_id)
                if parent is None or parent.status != "accepted":
                    raise ValueError(
                        "This revision draft is stale because its parent is no longer accepted."
                    )
                parent.status = "superseded"
            plan.status = "accepted"
            session.flush()
            return _plan_fact(session, plan)

    def add_feedback(
        self,
        *,
        session_id: int,
        outcome: str,
        perceived_exertion: int | None = None,
        reason_code: str | None = None,
        note: str | None = None,
        share_note_with_ai: bool = False,
    ) -> None:
        normalized_outcome = outcome.strip().lower()
        if normalized_outcome not in SUPPORTED_FEEDBACK_OUTCOMES:
            raise ValueError(f"Unsupported session outcome: {normalized_outcome}.")
        normalized_reason = _validate_feedback_reason(
            outcome=normalized_outcome, reason_code=reason_code
        )
        normalized_exertion = _validate_feedback_exertion(
            outcome=normalized_outcome, perceived_exertion=perceived_exertion
        )
        clean_note = None if note is None else note.strip() or None
        if share_note_with_ai and clean_note is None:
            raise ValueError("A shared feedback note cannot be empty.")
        with session_scope() as session:
            planned_session = get_planned_session(session, session_id=session_id)
            if planned_session is None:
                raise ValueError(f"No planned session exists with id {session_id}.")
            plan = get_training_plan(session, plan_id=planned_session.plan_id)
            if plan is None or plan.status != "accepted":
                raise ValueError(
                    "Feedback can only be saved for an accepted plan session."
                )
            upsert_session_feedback(
                session,
                planned_session_id=planned_session.id,
                outcome=normalized_outcome,
                perceived_exertion=normalized_exertion,
                reason_code=normalized_reason,
                note=clean_note,
                share_note_with_ai=share_note_with_ai,
            )

    def get_plan(self, *, plan_id: int) -> TrainingPlanFact:
        with session_scope() as session:
            plan = get_training_plan(session, plan_id=plan_id)
            if plan is None:
                raise ValueError(f"No plan exists with id {plan_id}.")
            return _plan_fact(session, plan)

    def list_plans(self) -> tuple[TrainingPlanFact, ...]:
        with session_scope() as session:
            return tuple(
                _plan_fact(session, plan) for plan in list_training_plans(session)
            )

    def _resolve_goal(
        self, *, as_of_date: date, race_id: int | None
    ) -> dict[str, object]:
        if race_id is None:
            return {
                "goal_mode": "general",
                "race_id": None,
                "race": None,
                "block_start_date": as_of_date,
                "block_end_date": as_of_date + timedelta(days=27),
            }
        with session_scope() as session:
            race = get_race_by_id(session, race_id)
        if race is None:
            raise ValueError(f"No race exists with id {race_id}.")
        if race.status != "active":
            raise ValueError("A cancelled race cannot define a new plan block.")
        if race.race_date < as_of_date:
            raise ValueError("A plan target race must be today or in the future.")
        return {
            "goal_mode": "race",
            "race_id": race.id,
            "race": {
                "id": race.id,
                "name": race.name,
                "sport_type": race.sport_type,
                "race_date": race.race_date.isoformat(),
                "distance_meters": race.distance_meters,
                "priority": race.priority,
                "desired_time_seconds": race.desired_time_seconds,
                "taper": resolved_taper(race),
            },
            "block_start_date": as_of_date,
            "block_end_date": race.race_date,
        }

    def _build_context(
        self,
        *,
        as_of_date: date,
        goal: dict[str, object],
        detailed_start_date: date,
        detailed_end_date: date,
        feedback: tuple[dict[str, object], ...],
        parent_plan: dict[str, object] | None,
    ) -> dict[str, object]:
        plan_readiness = self._plan_readiness_service.get_readiness(
            as_of_date=as_of_date
        )
        if plan_readiness.status != "ready":
            codes = ", ".join(blocker.code for blocker in plan_readiness.blockers)
            raise ValueError(
                f"Plan draft is blocked: {codes or 'insufficient history'}."
            )
        preference = self._preference_service.get_preference()
        if preference is None:
            raise ValueError("Set training preferences before creating a plan draft.")
        capacity = self._capacity_service.get_profile(end_date=as_of_date)
        performance_readiness = self._performance_service.get_readiness(
            end_date=as_of_date
        )
        training_response_trends = self._training_response_trend_service.get_trends(
            end_date=as_of_date
        )
        training_continuity = build_planning_continuity_facts(
            self._training_history_service.get_history(end_date=as_of_date)
        )
        active_principles = tuple(
            {
                "id": item.id,
                "statement": item.statement,
                "source_plan_id": item.source_plan_id,
            }
            for item, review_due in CoachingPrincipleService().list_active(
                as_of_date=as_of_date
            )
            if not review_due
        )
        personalization_evidence = PersonalizationEvidenceService().get_evidence(
            end_date=as_of_date
        )
        with session_scope() as session:
            context_events = get_context_events_in_date_range(
                session,
                start_date=detailed_start_date,
                end_date=detailed_end_date,
            )
        fact_catalog = _fact_catalog(
            as_of_date=as_of_date,
            goal=goal,
            detailed_start_date=detailed_start_date,
            detailed_end_date=detailed_end_date,
            plan_readiness=plan_readiness,
            capacity=capacity,
            performance_readiness=performance_readiness,
            preference=preference,
            context_events=context_events,
            feedback=feedback,
            parent_plan=parent_plan,
            training_response_trends=training_response_trends,
            training_continuity=training_continuity,
            active_principles=active_principles,
            personalization_evidence=personalization_evidence,
        )
        context = _json_safe({"schema_version": 6, "fact_catalog": fact_catalog})
        knowledge_library = load_knowledge_library()
        selected_briefs = select_for_plan_context(knowledge_library, context=context)
        context["knowledge_briefs"] = serialize_selected_briefs(
            knowledge_library, briefs=selected_briefs
        )
        return context

    def _validate_generated_plan(
        self,
        *,
        generated: GeneratedPlanDraft,
        detailed_start_date: date,
        detailed_end_date: date,
        block_start_date: date,
        block_end_date: date,
        performance_readiness: PerformanceReadiness,
        context: dict[str, object],
    ) -> None:
        if not generated.block_outline:
            raise ValueError("AI plan draft must contain a block outline.")
        if not generated.sessions:
            raise ValueError(
                "AI plan draft must contain at least one detailed session."
            )
        if not _is_complete_assessment(generated.coach_assessment):
            raise ValueError("AI plan draft must include a complete coach assessment.")
        _validate_fact_references(generated=generated, context=context)
        _validate_knowledge_references(generated=generated, context=context)
        _validate_availability(generated=generated, context=context)
        _validate_sport_mode(generated=generated, context=context)
        _validate_volume_boundaries(generated=generated, context=context)
        _validate_races_in_detailed_window(generated=generated, context=context)
        allowed_intensity = {
            fact.sport_type: set(fact.allowed_intensity_types)
            for fact in performance_readiness.sports
        }
        _validate_block_outline(
            outline=generated.block_outline,
            block_start_date=block_start_date,
            block_end_date=block_end_date,
        )
        for item in generated.sessions:
            if item.sport_type not in {"run", "ride"}:
                raise ValueError("AI plan draft contains an unsupported sport.")
            if not detailed_start_date <= item.scheduled_date <= detailed_end_date:
                raise ValueError(
                    "AI plan draft contains a session outside the detailed window."
                )
            if item.distance_meters is None and item.duration_seconds is None:
                raise ValueError("Each AI plan session needs distance or duration.")
            if item.sport_type == "ride" and item.distance_meters is None:
                raise ValueError("Each cycling plan session needs a distance target.")
            if item.sport_type == "ride" and item.duration_seconds is None:
                raise ValueError("Each cycling plan session needs a duration target.")
            if item.sport_type == "ride" and item.heart_rate_zone not in {
                1,
                2,
                3,
                4,
                5,
            }:
                raise ValueError(
                    "Each cycling plan session needs a configured Garmin heart-rate zone."
                )
            if item.sport_type == "run" and item.heart_rate_zone is not None:
                raise ValueError(
                    "Running plan sessions cannot include a cycling heart-rate zone."
                )
            _validate_session_target(
                session=item,
                allowed_intensity_types=allowed_intensity.get(item.sport_type, set()),
                performance_readiness=performance_readiness,
            )
            _validate_heart_rate_zone(
                session=item,
                performance_readiness=performance_readiness,
            )
            _validate_workout_steps(
                session=item,
                allowed_intensity_types=allowed_intensity.get(item.sport_type, set()),
                performance_readiness=performance_readiness,
            )

    def _persist_plan(
        self,
        *,
        parent_plan_id: int | None,
        goal: dict[str, object],
        as_of_date: date,
        detailed_start_date: date,
        detailed_end_date: date,
        generated: GeneratedPlanDraft,
        context: dict[str, object],
        performance_readiness: PerformanceReadiness,
        volume_exception: dict[str, object] | None,
    ) -> TrainingPlanFact:
        with session_scope() as session:
            if goal["race_id"] is not None:
                race = get_race_by_id(session, goal["race_id"])
                if race is None or race.status != "active":
                    raise ValueError("A plan for a cancelled race cannot be activated.")
            if parent_plan_id is not None:
                parent = get_training_plan(session, plan_id=parent_plan_id)
                if parent is None or parent.status != "accepted":
                    raise ValueError(
                        "This revision is stale because its parent is no longer active."
                    )
            stored_context = dict(context)
            if volume_exception is not None:
                stored_context["volume_exception"] = volume_exception
            plan = create_training_plan(
                session,
                TrainingPlan(
                    parent_plan_id=parent_plan_id,
                    status=(
                        "volume_exception_pending"
                        if volume_exception is not None
                        else "accepted"
                    ),
                    contract_version=CURRENT_PLAN_CONTRACT_VERSION,
                    goal_mode=goal["goal_mode"],
                    race_id=goal["race_id"],
                    as_of_date=as_of_date,
                    block_start_date=goal["block_start_date"],
                    block_end_date=goal["block_end_date"],
                    detailed_start_date=detailed_start_date,
                    detailed_end_date=detailed_end_date,
                    block_outline=[
                        {
                            "week_start": item.week_start.isoformat(),
                            "week_end": item.week_end.isoformat(),
                            "focus": item.focus,
                        }
                        for item in generated.block_outline
                    ],
                    context_snapshot=stored_context,
                    coach_assessment=_serialize_coach_assessment(
                        generated.coach_assessment
                    ),
                ),
            )
            for item in generated.sessions:
                create_planned_session(
                    session,
                    PlannedSession(
                        plan_id=plan.id,
                        scheduled_date=item.scheduled_date,
                        sport_type=item.sport_type,
                        purpose=item.purpose,
                        distance_meters=item.distance_meters,
                        duration_seconds=item.duration_seconds,
                        intensity_type=_legacy_intensity_type(item),
                        intensity_zone=item.heart_rate_zone,
                        intensity_target=_render_target_display(
                            item=item, performance_readiness=performance_readiness
                        ),
                        heart_rate_zone=item.heart_rate_zone,
                        target=_serialize_session_target(item.target),
                        workout_steps=_serialize_workout_steps(item.workout_steps),
                    ),
                )
            if volume_exception is None:
                _supersede_replaced_active_plans(
                    session=session,
                    plan=plan,
                    as_of_date=as_of_date,
                )
            return _plan_fact(session, plan)

    def _generate_validated(
        self,
        *,
        request: PlanGenerationRequest,
        validate: Callable[[GeneratedPlanDraft], None],
    ) -> GeneratedPlanDraft:
        """Give one rejected AI candidate a bounded, explicit correction attempt."""

        repair_instruction: str | None = None
        last_error: ValueError | None = None
        for _attempt in range(2):
            candidate = self._require_generator().generate(
                PlanGenerationRequest(
                    mode=request.mode,
                    context=request.context,
                    repair_instruction=repair_instruction,
                )
            )
            try:
                validate(candidate)
            except ValueError as error:
                last_error = error
                repair_instruction = str(error)
                continue
            return candidate
        if last_error is None:
            raise RuntimeError("Plan validation ended without a candidate or error.")
        raise last_error

    def _require_generator(self) -> PlanDraftGenerator:
        if self._generator is None:
            raise RuntimeError("A plan draft generator is required.")
        return self._generator


def _supersede_replaced_active_plans(
    *, session, plan: TrainingPlan, as_of_date: date
) -> None:
    """Version an explicit replacement only after its complete new plan exists."""

    for existing in list_training_plans(session):
        if existing.id == plan.id or existing.status != "accepted":
            continue
        if existing.block_start_date <= as_of_date <= existing.block_end_date:
            existing.status = "superseded"


def _validate_plan_days(days: int) -> int:
    if days not in SUPPORTED_PLAN_DAYS:
        raise ValueError("Detailed plan days must be 7 or 14.")
    return days


def _validate_feedback_exertion(
    *, outcome: str, perceived_exertion: int | None
) -> int | None:
    if perceived_exertion is None:
        return None
    if outcome not in {"completed", "completed_limited"}:
        raise ValueError("RPE can only be saved for a completed session.")
    if (
        not isinstance(perceived_exertion, int)
        or isinstance(perceived_exertion, bool)
        or not 1 <= perceived_exertion <= 10
    ):
        raise ValueError("RPE must be an integer from 1 to 10.")
    return perceived_exertion


def _validate_feedback_reason(*, outcome: str, reason_code: str | None) -> str | None:
    if reason_code is None:
        return None
    normalized_reason = reason_code.strip().lower()
    if outcome not in {"completed_limited", "skipped"}:
        raise ValueError(
            "A structured reason can only be saved for a limited or skipped session."
        )
    if normalized_reason not in SUPPORTED_FEEDBACK_REASON_CODES:
        raise ValueError(f"Unsupported feedback reason: {normalized_reason}.")
    return normalized_reason


def _deserialize_outline_item(item: dict[str, object]):
    from pace.planning.draft_models import BlockOutlineItem

    return BlockOutlineItem(
        week_start=date.fromisoformat(str(item["week_start"])),
        week_end=date.fromisoformat(str(item["week_end"])),
        focus=str(item["focus"]),
    )


def _plan_fact(session, plan: TrainingPlan) -> TrainingPlanFact:
    sessions = get_sessions_for_plan(session, plan_id=plan.id)
    feedback = get_feedback_for_sessions(
        session, session_ids=[item.id for item in sessions]
    )
    return TrainingPlanFact(
        id=plan.id,
        parent_plan_id=plan.parent_plan_id,
        status=plan.status,
        contract_version=plan.contract_version,
        goal_mode=plan.goal_mode,
        race_id=plan.race_id,
        as_of_date=plan.as_of_date,
        block_start_date=plan.block_start_date,
        block_end_date=plan.block_end_date,
        detailed_start_date=plan.detailed_start_date,
        detailed_end_date=plan.detailed_end_date,
        block_outline=tuple(plan.block_outline),
        sessions=tuple(
            PlanSessionFact(
                id=item.id,
                scheduled_date=item.scheduled_date,
                sport_type=item.sport_type,
                purpose=item.purpose,
                distance_meters=item.distance_meters,
                duration_seconds=item.duration_seconds,
                heart_rate_zone=item.heart_rate_zone,
                target=_session_target_fact(item),
                target_display=_session_target_display(item),
                feedback_outcome=(
                    None if item.id not in feedback else feedback[item.id].outcome
                ),
                feedback_perceived_exertion=(
                    None
                    if item.id not in feedback
                    else feedback[item.id].perceived_exertion
                ),
                feedback_reason_code=(
                    None if item.id not in feedback else feedback[item.id].reason_code
                ),
                workout_steps=_workout_steps_fact(item),
            )
            for item in sessions
        ),
        coach_assessment=_coach_assessment_fact(
            plan.coach_assessment,
            context_snapshot=plan.context_snapshot,
        ),
        volume_exception=_stored_volume_exception(plan.context_snapshot),
    )


def _json_safe(value):
    """Serialize selected local facts before an AI call or JSON database snapshot."""

    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _serialize_coach_assessment(assessment) -> dict[str, object]:
    return {
        "fact_references": list(assessment.fact_references),
        "inferences": list(assessment.inferences),
        "rationale": assessment.rationale,
        "uncertainties": list(assessment.uncertainties),
        "coaching_principles": list(assessment.coaching_principles),
        "knowledge_references": list(assessment.knowledge_references),
    }


def _coach_assessment_fact(
    value: dict[str, object] | None,
    *,
    context_snapshot: dict[str, object],
) -> CoachAssessmentFact:
    """Render stored AI reasoning explicitly as reasoning, never as Pace facts."""

    value = value or {}
    fact_references = _stored_text_tuple(value.get("fact_references"))
    fact_catalog = context_snapshot.get("fact_catalog")
    if not isinstance(fact_catalog, dict):
        fact_catalog = {}
    return CoachAssessmentFact(
        fact_references=fact_references,
        observed_facts=tuple(
            _render_catalog_fact(fact_catalog[reference])
            for reference in fact_references
            if isinstance(fact_catalog.get(reference), dict)
        ),
        inferences=_stored_text_tuple(value.get("inferences")),
        rationale=str(value.get("rationale") or ""),
        uncertainties=_stored_text_tuple(value.get("uncertainties")),
        coaching_principles=_stored_text_tuple(value.get("coaching_principles")),
        knowledge_references=_stored_text_tuple(value.get("knowledge_references")),
    )


def _stored_text_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _fact_catalog(
    *,
    as_of_date,
    goal,
    detailed_start_date,
    detailed_end_date,
    plan_readiness,
    capacity,
    performance_readiness,
    preference,
    context_events,
    feedback,
    parent_plan,
    training_response_trends,
    training_continuity,
    active_principles,
    personalization_evidence,
) -> dict[str, dict[str, object]]:
    """Expose selected deterministic facts by stable IDs for AI citation."""

    return {
        "as_of_date": _catalog_entry("python_derived", {"date": as_of_date}),
        "goal": _catalog_entry("explicit_user_or_python_derived", goal),
        "detailed_window": _catalog_entry(
            "python_derived",
            {"start_date": detailed_start_date, "end_date": detailed_end_date},
        ),
        "planning_readiness": _catalog_entry(
            "python_derived", _planning_readiness_for_selected_goal(plan_readiness)
        ),
        "capacity_profile": _catalog_entry("garmin_verified", asdict(capacity)),
        "performance_readiness": _catalog_entry(
            "garmin_verified", asdict(performance_readiness)
        ),
        "training_preference": _catalog_entry(
            "explicit_athlete_preference",
            {
                "sport_role": preference.sport_role,
                "coaching_ambition": getattr(
                    preference, "coaching_ambition", "balanced"
                ),
                "available_days": preference.available_days,
                "base_running_distance_ceiling_km": getattr(
                    preference, "base_running_distance_ceiling_km", None
                ),
                "base_cycling_duration_ceiling_hours": getattr(
                    preference, "base_cycling_duration_ceiling_hours", None
                ),
                "base_total_duration_ceiling_hours": getattr(
                    preference, "base_total_duration_ceiling_hours", None
                ),
            },
        ),
        "relevant_context": _catalog_entry(
            "athlete_reported_metadata",
            [
                {
                    "event_type": event.event_type,
                    "start_date": event.start_date,
                    "end_date": event.end_date,
                    "status": event.status,
                }
                for event in context_events
            ],
        ),
        "feedback": _catalog_entry("athlete_reported", list(feedback)),
        "training_response_trends": _catalog_entry(
            "athlete_reported_python_derived", asdict(training_response_trends)
        ),
        "training_continuity": _catalog_entry("garmin_verified", training_continuity),
        "athlete_confirmed_coach_principles": _catalog_entry(
            "explicit_athlete_confirmation", active_principles
        ),
        "personalization_evidence": _catalog_entry(
            "athlete_reported_python_derived", asdict(personalization_evidence)
        ),
        "parent_plan": _catalog_entry("local_accepted_plan", parent_plan),
    }


def _catalog_entry(provenance: str, value: object) -> dict[str, object]:
    return {"provenance": provenance, "value": _json_safe(value)}


def _render_catalog_fact(entry: dict[str, object]) -> str:
    provenance = entry.get("provenance")
    value = entry.get("value")
    return json.dumps(
        {"provenance": provenance, "value": value},
        ensure_ascii=False,
        sort_keys=True,
    )


def _validate_races_in_detailed_window(
    *, generated: GeneratedPlanDraft, context: dict[str, object]
) -> None:
    """Require only the athlete-selected target race, never every stored race."""

    catalog = context.get("fact_catalog")
    if not isinstance(catalog, dict):
        return
    detailed_window = _catalog_value(catalog, "detailed_window")
    goal = _catalog_value(catalog, "goal")
    if not isinstance(detailed_window, dict) or not isinstance(goal, dict):
        return
    try:
        start = date.fromisoformat(str(detailed_window["start_date"]))
        end = date.fromisoformat(str(detailed_window["end_date"]))
    except KeyError, ValueError:
        return
    race = goal.get("race")
    if not isinstance(race, dict):
        return
    try:
        race_date = date.fromisoformat(str(race["race_date"]))
    except KeyError, ValueError:
        return
    if not start <= race_date <= end:
        return
    sport_type = race.get("sport_type")
    if not any(
        session.scheduled_date == race_date and session.sport_type == sport_type
        for session in generated.sessions
    ):
        raise ValueError(
            "AI plan draft omitted the selected target race inside the detailed window."
        )


def _planning_readiness_for_selected_goal(plan_readiness) -> dict[str, object]:
    """Keep readiness gates, but never make stored races implicit plan inputs."""

    value = asdict(plan_readiness)
    value["upcoming_races"] = []
    return value


def _catalog_value(catalog: dict[str, object], key: str) -> object:
    entry = catalog.get(key)
    return entry.get("value") if isinstance(entry, dict) else None


def _validate_fact_references(
    *, generated: GeneratedPlanDraft, context: dict[str, object]
) -> None:
    fact_catalog = context.get("fact_catalog")
    if not isinstance(fact_catalog, dict):
        raise ValueError("Plan draft context is missing the fact catalog.")
    references = generated.coach_assessment.fact_references
    if not references:
        raise ValueError(
            "AI plan draft must reference at least one selected Pace fact."
        )
    unknown = set(references).difference(fact_catalog)
    if unknown:
        raise ValueError(
            "AI plan draft referenced facts outside the selected Pace fact catalog."
        )


def _validate_knowledge_references(
    *, generated: GeneratedPlanDraft, context: dict[str, object]
) -> None:
    selected = context.get("knowledge_briefs")
    if not isinstance(selected, dict):
        raise ValueError("Plan draft context is missing selected knowledge briefs.")
    briefs = selected.get("briefs")
    if not isinstance(briefs, list):
        raise ValueError("Plan draft context has invalid knowledge briefs.")
    allowed_ids = {
        item.get("id")
        for item in briefs
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    references = generated.coach_assessment.knowledge_references
    if set(references).difference(allowed_ids):
        raise ValueError(
            "AI plan draft cited knowledge outside the selected knowledge briefs."
        )


def _validate_availability(
    *, generated: GeneratedPlanDraft, context: dict[str, object]
) -> None:
    """Enforce athlete-supplied weekdays and explicit time ceilings in Python."""

    fact_catalog = context.get("fact_catalog")
    if not isinstance(fact_catalog, dict):
        raise ValueError("Plan draft context is missing the fact catalog.")
    preference_entry = fact_catalog.get("training_preference")
    if not isinstance(preference_entry, dict):
        raise ValueError("Plan draft context is missing training preferences.")
    preference = preference_entry.get("value")
    if not isinstance(preference, dict):
        raise ValueError("Plan draft context is missing training preferences.")
    available_days = preference.get("available_days")
    if not isinstance(available_days, list):
        raise ValueError("Plan draft context has invalid training preferences.")
    limits_by_day: dict[str, int | None] = {}
    for item in available_days:
        if not isinstance(item, dict):
            raise ValueError("Plan draft context has invalid availability entries.")
        day = item.get("day")
        minutes = item.get("minutes")
        if day not in WEEKDAY_CODES or (
            minutes is not None and not isinstance(minutes, int)
        ):
            raise ValueError("Plan draft context has invalid availability entries.")
        limits_by_day[day] = minutes

    duration_by_date: dict[date, int] = {}
    for session in generated.sessions:
        day = WEEKDAY_CODES[session.scheduled_date.weekday()]
        if day not in limits_by_day:
            raise ValueError(
                "AI plan draft scheduled a session outside athlete availability."
            )
        duration_by_date[session.scheduled_date] = duration_by_date.get(
            session.scheduled_date, 0
        ) + (session.duration_seconds or 0)
        if limits_by_day[day] is not None and session.duration_seconds is None:
            raise ValueError(
                "A time-limited available day requires a session duration."
            )

    for scheduled_date, total_seconds in duration_by_date.items():
        day = WEEKDAY_CODES[scheduled_date.weekday()]
        minutes_limit = limits_by_day[day]
        if minutes_limit is not None and total_seconds > minutes_limit * 60:
            raise ValueError("AI plan draft exceeds athlete availability on one day.")


def _validate_sport_mode(
    *, generated: GeneratedPlanDraft, context: dict[str, object]
) -> None:
    """Treat only-sport selections as athlete-owned hard boundaries."""

    catalog = context.get("fact_catalog")
    preference_entry = (
        catalog.get("training_preference") if isinstance(catalog, dict) else None
    )
    preference = (
        preference_entry.get("value") if isinstance(preference_entry, dict) else None
    )
    role = preference.get("sport_role") if isinstance(preference, dict) else None
    allowed = {"run", "ride"}
    if role == "run_only":
        allowed = {"run"}
    elif role == "ride_only":
        allowed = {"ride"}
    if any(session.sport_type not in allowed for session in generated.sessions):
        raise ValueError(
            "AI plan draft used a sport outside the athlete's selected sport mode."
        )


def _validate_volume_boundaries(
    *, generated: GeneratedPlanDraft, context: dict[str, object]
) -> None:
    """Enforce base ceilings; only a selected race may request an exception."""

    breaches = _weekly_volume_breaches(generated=generated, context=context)
    if not breaches:
        return
    catalog = context.get("fact_catalog")
    goal = _catalog_value(catalog, "goal") if isinstance(catalog, dict) else None
    if isinstance(goal, dict) and goal.get("goal_mode") == "race":
        return
    first = breaches[0]
    metrics = ", ".join(item["metric"] for item in first["breaches"])
    raise ValueError(
        "AI plan draft exceeds the athlete's hard base-volume ceiling "
        f"for {metrics}. A general plan cannot request a race-volume exception."
    )


def _volume_exception_for_generated(
    *, generated: GeneratedPlanDraft, context: dict[str, object]
) -> dict[str, object] | None:
    breaches = _weekly_volume_breaches(generated=generated, context=context)
    if not breaches:
        return None
    return {
        "approved": False,
        "rationale": generated.coach_assessment.rationale,
        "weeks": breaches,
    }


def _weekly_volume_breaches(
    *, generated: GeneratedPlanDraft, context: dict[str, object]
) -> list[dict[str, object]]:
    catalog = context.get("fact_catalog")
    preference = (
        _catalog_value(catalog, "training_preference")
        if isinstance(catalog, dict)
        else None
    )
    if not isinstance(preference, dict):
        raise ValueError("Plan draft context is missing training preferences.")
    run_ceiling = _optional_positive_number(
        preference.get("base_running_distance_ceiling_km"),
        label="base running ceiling",
    )
    ride_ceiling = _optional_positive_number(
        preference.get("base_cycling_duration_ceiling_hours"),
        label="base cycling ceiling",
    )
    total_ceiling = _optional_positive_number(
        preference.get("base_total_duration_ceiling_hours"),
        label="base total-time ceiling",
    )
    if run_ceiling is None and ride_ceiling is None and total_ceiling is None:
        return []

    weekly: dict[date, dict[str, float]] = {}
    for item in generated.sessions:
        week_start = item.scheduled_date - timedelta(days=item.scheduled_date.weekday())
        values = weekly.setdefault(
            week_start,
            {
                "running_distance_km": 0.0,
                "cycling_duration_hours": 0.0,
                "total_duration_hours": 0.0,
            },
        )
        if item.sport_type == "run" and run_ceiling is not None:
            if item.distance_meters is None:
                raise ValueError(
                    "Each running session needs a distance while a base running ceiling is set."
                )
            values["running_distance_km"] += item.distance_meters / 1_000
        if item.sport_type == "ride" and ride_ceiling is not None:
            if item.duration_seconds is None:
                raise ValueError(
                    "Each cycling session needs a duration while a base cycling ceiling is set."
                )
            values["cycling_duration_hours"] += item.duration_seconds / 3_600
        if total_ceiling is not None:
            if item.duration_seconds is None:
                raise ValueError(
                    "Each session needs a duration while a base total-time ceiling is set."
                )
            values["total_duration_hours"] += item.duration_seconds / 3_600

    boundaries = (
        ("running_distance_km", run_ceiling, "km"),
        ("cycling_duration_hours", ride_ceiling, "hours"),
        ("total_duration_hours", total_ceiling, "hours"),
    )
    result: list[dict[str, object]] = []
    for week_start, values in sorted(weekly.items()):
        week_breaches = [
            {
                "metric": metric,
                "ceiling": ceiling,
                "proposed": round(values[metric], 3),
                "unit": unit,
            }
            for metric, ceiling, unit in boundaries
            if ceiling is not None and values[metric] > ceiling + 1e-9
        ]
        if week_breaches:
            result.append(
                {
                    "week_start": week_start.isoformat(),
                    "week_end": (week_start + timedelta(days=6)).isoformat(),
                    "breaches": week_breaches,
                }
            )
    return result


def _optional_positive_number(value: object, *, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"Plan draft context has an invalid {label}.")
    return float(value)


def _stored_volume_exception(
    context_snapshot: dict[str, object],
) -> VolumeExceptionFact | None:
    value = context_snapshot.get("volume_exception")
    if not isinstance(value, dict):
        return None
    weeks_value = value.get("weeks")
    if not isinstance(weeks_value, list):
        return None
    weeks: list[WeeklyVolumeExceptionFact] = []
    try:
        for week in weeks_value:
            if not isinstance(week, dict) or not isinstance(week.get("breaches"), list):
                return None
            breaches = tuple(
                VolumeBoundaryBreachFact(
                    metric=str(breach["metric"]),
                    ceiling=float(breach["ceiling"]),
                    proposed=float(breach["proposed"]),
                    unit=str(breach["unit"]),
                )
                for breach in week["breaches"]
                if isinstance(breach, dict)
            )
            weeks.append(
                WeeklyVolumeExceptionFact(
                    week_start=date.fromisoformat(str(week["week_start"])),
                    week_end=date.fromisoformat(str(week["week_end"])),
                    breaches=breaches,
                )
            )
    except KeyError, TypeError, ValueError:
        return None
    return VolumeExceptionFact(
        approved=bool(value.get("approved")),
        rationale=str(value.get("rationale") or ""),
        weeks=tuple(weeks),
    )


def _validate_block_outline(
    *, outline, block_start_date: date, block_end_date: date
) -> None:
    """Require sorted, contiguous phases that describe the whole plan block."""

    expected_start = block_start_date
    for item in outline:
        if item.week_start != expected_start or item.week_end < item.week_start:
            raise ValueError(
                "AI plan draft block outline must be sorted and contiguous."
            )
        if item.week_end > block_end_date:
            raise ValueError("AI plan draft contains an outline outside the block.")
        expected_start = item.week_end + timedelta(days=1)
    if expected_start != block_end_date + timedelta(days=1):
        raise ValueError("AI plan draft block outline must cover the full plan block.")


def _is_complete_assessment(assessment) -> bool:
    return bool(
        _has_nonempty_texts(assessment.fact_references)
        and _has_nonempty_texts(assessment.inferences)
        and isinstance(assessment.rationale, str)
        and assessment.rationale.strip()
        and _has_nonempty_texts(assessment.uncertainties)
        and _has_nonempty_texts(assessment.coaching_principles)
    )


def _has_nonempty_texts(values: object) -> bool:
    return (
        isinstance(values, tuple)
        and bool(values)
        and all(isinstance(value, str) and value.strip() for value in values)
    )


def _has_complete_assessment(value: dict[str, object] | None) -> bool:
    if not isinstance(value, dict):
        return False
    text_list_fields = (
        "fact_references",
        "inferences",
        "uncertainties",
        "coaching_principles",
    )
    if any(not _stored_text_tuple(value.get(field)) for field in text_list_fields):
        return False
    return isinstance(value.get("rationale"), str) and bool(value["rationale"].strip())


def _goal_from_parent(parent: TrainingPlan) -> dict[str, object]:
    fact_catalog = parent.context_snapshot.get("fact_catalog")
    snapshot_goal = (
        fact_catalog.get("goal", {}).get("value")
        if isinstance(fact_catalog, dict)
        else None
    )
    if not isinstance(snapshot_goal, dict):
        snapshot_goal = {}
    return {
        "goal_mode": parent.goal_mode,
        "race_id": parent.race_id,
        "race": snapshot_goal.get("race"),
        "block_start_date": parent.block_start_date,
        "block_end_date": parent.block_end_date,
    }


def _parent_plan_context(*, parent, sessions, feedback_by_session) -> dict[str, object]:
    """Send a bounded parent-plan contract to a revision, not free-form history."""

    return {
        "id": parent.id,
        "goal_mode": parent.goal_mode,
        "race_id": parent.race_id,
        "block_start_date": parent.block_start_date.isoformat(),
        "block_end_date": parent.block_end_date.isoformat(),
        "block_outline": parent.block_outline,
        "sessions": [
            {
                "id": session.id,
                "scheduled_date": session.scheduled_date.isoformat(),
                "sport_type": session.sport_type,
                "purpose": session.purpose,
                "distance_meters": session.distance_meters,
                "duration_seconds": session.duration_seconds,
                "heart_rate_zone": session.heart_rate_zone,
                "target": _serialize_session_target(_session_target_draft(session)),
                "target_display": _session_target_display(session),
                "workout_steps": _serialize_stored_workout_steps(session),
                "feedback_outcome": (
                    None
                    if session.id not in feedback_by_session
                    else feedback_by_session[session.id].outcome
                ),
            }
            for session in sessions
        ],
    }


def _validate_heart_rate_zone(
    *, session, performance_readiness: PerformanceReadiness
) -> None:
    """Require a cycling zone that exists in the athlete's saved profile."""

    if session.heart_rate_zone is None:
        return
    configured_zones = {
        zone["zone"]
        for sport in performance_readiness.sports
        if sport.sport_type == session.sport_type
        for zone in sport.heart_rate_zones
    }
    if session.heart_rate_zone not in configured_zones:
        raise ValueError(
            "AI plan draft used a heart-rate zone not configured for this sport."
        )


def _validate_session_target(
    *,
    session,
    allowed_intensity_types: set[str],
    performance_readiness: PerformanceReadiness,
) -> None:
    target = session.target
    numeric_fields = (
        target.rpe_min,
        target.rpe_max,
        target.pace_seconds_per_km,
        target.power_watts,
    )
    evidence_by_reference = {
        evidence.reference_id: evidence
        for sport in performance_readiness.sports
        for evidence in sport.intensity_evidence
    }
    if target.kind == "none":
        if (
            any(value is not None for value in numeric_fields)
            or target.evidence_reference_id
        ):
            raise ValueError(
                "A none target cannot include numeric values or an evidence reference."
            )
        return
    if target.kind == "rpe":
        if (
            target.rpe_min is None
            or target.rpe_max is None
            or not 1 <= target.rpe_min <= target.rpe_max <= 10
            or target.pace_seconds_per_km is not None
            or target.power_watts is not None
            or target.evidence_reference_id is not None
        ):
            raise ValueError(
                "An RPE target must contain only an RPE range from 1 to 10."
            )
        return
    if target.kind not in allowed_intensity_types:
        raise ValueError(
            f"AI plan draft proposed {target.kind} without {session.sport_type} eligibility."
        )
    evidence = evidence_by_reference.get(target.evidence_reference_id)
    if evidence is None or evidence.sport_type != session.sport_type:
        raise ValueError("AI plan draft target lacks eligible same-sport evidence.")
    if target.kind == "pace":
        if (
            session.sport_type != "run"
            or target.pace_seconds_per_km is None
            or not 120 <= target.pace_seconds_per_km <= 1_200
            or target.rpe_min is not None
            or target.rpe_max is not None
            or target.power_watts is not None
            or evidence.average_speed_mps is None
        ):
            raise ValueError(
                "A pace target must cite numeric verified running evidence."
            )
        return
    if target.kind == "power":
        if (
            session.sport_type != "ride"
            or target.power_watts is None
            or not 30 <= target.power_watts <= 2_000
            or target.rpe_min is not None
            or target.rpe_max is not None
            or target.pace_seconds_per_km is not None
            or evidence.protocol != "ride_20min_power_test"
            or evidence.qualifying_power_watts is None
        ):
            raise ValueError(
                "A power target must cite a verified 20-minute cycling power test."
            )
        return
    raise ValueError("AI plan draft had an unsupported target kind.")


def _validate_workout_steps(
    *,
    session,
    allowed_intensity_types: set[str],
    performance_readiness: PerformanceReadiness,
) -> None:
    """Validate each generated workout block with the same evidence gates as its pass."""

    if not session.workout_steps:
        raise ValueError(
            "Each AI plan session needs at least one structured workout step."
        )
    for step in session.workout_steps:
        if step.kind not in {"warmup", "steady", "interval", "cooldown"}:
            raise ValueError("AI plan draft contains an unsupported workout-step kind.")
        if step.distance_meters is None and step.duration_seconds is None:
            raise ValueError("Each workout step needs distance or duration.")
        if step.kind == "interval":
            if step.repetitions < 2:
                raise ValueError(
                    "An interval workout step needs at least two repetitions."
                )
            if (
                step.recovery_distance_meters is None
                and step.recovery_duration_seconds is None
            ) or step.recovery_target is None:
                raise ValueError(
                    "An interval workout step needs recovery duration or distance and target."
                )
        elif (
            step.repetitions != 1
            or step.recovery_distance_meters is not None
            or step.recovery_duration_seconds is not None
            or step.recovery_target is not None
        ):
            raise ValueError(
                "Only interval workout steps may use repetitions or recovery."
            )
        _validate_session_target(
            session=_WorkoutStepSession(session.sport_type, step.target),
            allowed_intensity_types=allowed_intensity_types,
            performance_readiness=performance_readiness,
        )
        if step.recovery_target is not None:
            _validate_session_target(
                session=_WorkoutStepSession(session.sport_type, step.recovery_target),
                allowed_intensity_types=allowed_intensity_types,
                performance_readiness=performance_readiness,
            )


class _WorkoutStepSession:
    """Small compatibility view for target validation on a workout block."""

    def __init__(self, sport_type: str, target: SessionTargetDraft) -> None:
        self.sport_type = sport_type
        self.target = target


def _render_target_display(*, item, performance_readiness: PerformanceReadiness) -> str:
    """Render targets from structured fields; never persist free AI target text."""

    parts: list[str] = []
    if item.heart_rate_zone is not None:
        for sport in performance_readiness.sports:
            if sport.sport_type != item.sport_type:
                continue
            for zone in sport.heart_rate_zones:
                if zone["zone"] == item.heart_rate_zone:
                    parts.append(
                        f"Z{item.heart_rate_zone} "
                        f"({zone['lower_bpm']}–{zone['upper_bpm']} bpm)"
                    )
                    break
    target = item.target
    if target.kind == "rpe":
        parts.append(f"RPE {target.rpe_min}–{target.rpe_max}")
    elif target.kind == "pace":
        minutes, seconds = divmod(target.pace_seconds_per_km or 0, 60)
        parts.append(f"{minutes}:{seconds:02d} min/km")
    elif target.kind == "power":
        parts.append(f"{target.power_watts} W")
    return " | ".join(parts) or "No primary intensity target"


def _legacy_intensity_type(item) -> str:
    return "hr_zone" if item.heart_rate_zone is not None else item.target.kind


def _serialize_session_target(target: SessionTargetDraft) -> dict[str, object]:
    return {
        "kind": target.kind,
        "rpe_min": target.rpe_min,
        "rpe_max": target.rpe_max,
        "pace_seconds_per_km": target.pace_seconds_per_km,
        "power_watts": target.power_watts,
        "evidence_reference_id": target.evidence_reference_id,
    }


def _serialize_workout_steps(
    steps: tuple[WorkoutStepDraft, ...],
) -> list[dict[str, object]]:
    return [
        {
            "kind": step.kind,
            "repetitions": step.repetitions,
            "distance_meters": step.distance_meters,
            "duration_seconds": step.duration_seconds,
            "target": _serialize_session_target(step.target),
            "recovery_distance_meters": step.recovery_distance_meters,
            "recovery_duration_seconds": step.recovery_duration_seconds,
            "recovery_target": (
                None
                if step.recovery_target is None
                else _serialize_session_target(step.recovery_target)
            ),
            "instruction": step.instruction,
        }
        for step in steps
    ]


def _serialize_stored_workout_steps(session) -> list[dict[str, object]]:
    """Return plan snapshots as JSON-safe context, tolerating pre-v3 plans."""

    return (
        list(session.workout_steps) if isinstance(session.workout_steps, list) else []
    )


def _session_target_draft(session) -> SessionTargetDraft:
    """Read current stored structured targets, with a safe legacy representation."""

    target = _session_target_fact(session)
    return SessionTargetDraft(
        kind=target.kind,
        rpe_min=target.rpe_min,
        rpe_max=target.rpe_max,
        pace_seconds_per_km=target.pace_seconds_per_km,
        power_watts=target.power_watts,
        evidence_reference_id=target.evidence_reference_id,
    )


def _session_target_fact(session) -> SessionTargetFact:
    target = session.target
    if not isinstance(target, dict):
        return SessionTargetFact(
            kind="legacy",
            rpe_min=None,
            rpe_max=None,
            pace_seconds_per_km=None,
            power_watts=None,
            evidence_reference_id=None,
        )
    return SessionTargetFact(
        kind=str(target.get("kind") or "none"),
        rpe_min=_stored_int(target.get("rpe_min")),
        rpe_max=_stored_int(target.get("rpe_max")),
        pace_seconds_per_km=_stored_int(target.get("pace_seconds_per_km")),
        power_watts=_stored_int(target.get("power_watts")),
        evidence_reference_id=(
            target.get("evidence_reference_id")
            if isinstance(target.get("evidence_reference_id"), str)
            else None
        ),
    )


def _workout_steps_fact(session) -> tuple[WorkoutStepFact, ...]:
    raw_steps = session.workout_steps if isinstance(session.workout_steps, list) else []
    steps: list[WorkoutStepFact] = []
    for raw in raw_steps:
        if not isinstance(raw, dict):
            continue
        target = _session_target_fact_from_raw(raw.get("target"))
        recovery_raw = raw.get("recovery_target")
        steps.append(
            WorkoutStepFact(
                kind=str(raw.get("kind") or "steady"),
                repetitions=_stored_int(raw.get("repetitions")) or 1,
                distance_meters=_stored_float(raw.get("distance_meters")),
                duration_seconds=_stored_int(raw.get("duration_seconds")),
                target=target,
                recovery_distance_meters=_stored_float(
                    raw.get("recovery_distance_meters")
                ),
                recovery_duration_seconds=_stored_int(
                    raw.get("recovery_duration_seconds")
                ),
                recovery_target=(
                    _session_target_fact_from_raw(recovery_raw)
                    if isinstance(recovery_raw, dict)
                    else None
                ),
                instruction=str(raw.get("instruction") or ""),
            )
        )
    return tuple(steps)


def _session_target_fact_from_raw(raw: object) -> SessionTargetFact:
    if not isinstance(raw, dict):
        return SessionTargetFact("none", None, None, None, None, None)
    return SessionTargetFact(
        kind=str(raw.get("kind") or "none"),
        rpe_min=_stored_int(raw.get("rpe_min")),
        rpe_max=_stored_int(raw.get("rpe_max")),
        pace_seconds_per_km=_stored_int(raw.get("pace_seconds_per_km")),
        power_watts=_stored_int(raw.get("power_watts")),
        evidence_reference_id=(
            raw.get("evidence_reference_id")
            if isinstance(raw.get("evidence_reference_id"), str)
            else None
        ),
    )


def _session_target_display(session) -> str:
    # Current plans persist display text produced by _render_target_display,
    # never text supplied by the model. Keeping it also preserves the saved
    # Garmin zone bounds when a plan is read later.
    if session.target is not None:
        return session.intensity_target
    return session.intensity_target


def _stored_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _stored_float(value: object) -> float | None:
    return (
        float(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else None
    )
