"""Make a read-only comparison of a planned workout and same-day Garmin facts."""

from pace.database.session import session_scope
from pace.repositories.activity_repository import get_activities_in_date_range
from pace.repositories.activity_performance_detail_repository import (
    get_details_for_activities,
)
from pace.repositories.training_plan_repository import (
    get_feedback_for_sessions,
    get_planned_session,
    get_training_plan,
)
from pace.services.training_plan_service import _workout_steps_fact
from pace.timezones import athlete_local_date
from pace.workouts.models import (
    ActivitySplitFact,
    MatchingActivityFact,
    PlannedActualComparison,
    WorkoutEvaluation,
)


class WorkoutEvaluationService:
    """Never infer completion: Garmin matches are candidates, feedback remains authoritative."""

    def evaluate(self, *, session_id: int) -> WorkoutEvaluation:
        with session_scope() as session:
            planned = get_planned_session(session, session_id=session_id)
            if planned is None:
                raise ValueError(f"No planned session exists with id {session_id}.")
            plan = get_training_plan(session, plan_id=planned.plan_id)
            if plan is None:
                raise ValueError("The planned session has no readable parent plan.")
            if plan.status not in {"accepted", "superseded"}:
                raise ValueError("Only accepted or earlier accepted plan sessions can be evaluated.")
            feedback = get_feedback_for_sessions(session, session_ids=[planned.id]).get(planned.id)
            activities = tuple(
                activity
                for activity in get_activities_in_date_range(
                    session,
                    start_date=planned.scheduled_date,
                    end_date=planned.scheduled_date,
                )
                if activity.sport_type == planned.sport_type
                and athlete_local_date(activity.start_time) == planned.scheduled_date
            )
            details = get_details_for_activities(
                session, activity_ids=[activity.id for activity in activities]
            )
            matches = tuple(
                MatchingActivityFact(
                    provider_activity_id=activity.provider_activity_id,
                    activity_date=athlete_local_date(activity.start_time),
                    distance_meters=activity.distance_meters,
                    duration_seconds=activity.duration_seconds,
                    detail_available=activity.id in details,
                    splits=_split_facts(details.get(activity.id)),
                )
                for activity in activities
            )
            planned_steps = _workout_steps_fact(planned)
            comparisons = tuple(
                _comparison(planned=planned, steps=planned_steps, activity=activity, detail=details.get(activity.id))
                for activity in activities
            )
            limitations = ["garmin_match_is_not_proof_of_step_completion"]
            if feedback is None:
                limitations.append("explicit_feedback_missing")
            if not matches:
                limitations.append("no_same_day_same_sport_garmin_activity")
            return WorkoutEvaluation(
                session_id=planned.id,
                plan_id=planned.plan_id,
                scheduled_date=planned.scheduled_date,
                sport_type=planned.sport_type,
                planned_steps=planned_steps,
                feedback_outcome=None if feedback is None else feedback.outcome,
                feedback_perceived_exertion=(
                    None if feedback is None else feedback.perceived_exertion
                ),
                feedback_reason_code=None if feedback is None else feedback.reason_code,
                matching_activities=matches,
                comparisons=comparisons,
                limitations=tuple(limitations),
            )


def _split_facts(detail) -> tuple[ActivitySplitFact, ...]:
    if detail is None or not isinstance(detail.splits, list):
        return ()
    facts = []
    for item in detail.splits:
        if not isinstance(item, dict):
            continue
        facts.append(
            ActivitySplitFact(
                split_number=_int_or_none(item.get("split_number")) or len(facts) + 1,
                duration_seconds=_int_or_none(item.get("duration_seconds")),
                distance_meters=_float_or_none(item.get("distance_meters")),
                average_heart_rate=_int_or_none(item.get("average_heart_rate")),
                average_speed_mps=_float_or_none(item.get("average_speed_mps")),
                average_cadence=_float_or_none(item.get("average_cadence")),
                average_power=_float_or_none(item.get("average_power")),
            )
        )
    return tuple(facts)


def _comparison(*, planned, steps, activity, detail) -> PlannedActualComparison:
    actual_duration = (
        detail.duration_seconds
        if detail is not None and detail.duration_seconds is not None
        else activity.duration_seconds
    )
    actual_distance = (
        detail.distance_meters
        if detail is not None and detail.distance_meters is not None
        else activity.distance_meters
    )
    split_count = len(detail.splits) if detail is not None else 0
    planned_repetitions = sum(
        step.repetitions for step in steps if step.kind == "interval"
    )
    limitations = ["summary_comparison_only"]
    if detail is None:
        limitations.append("performance_detail_missing")
    if planned_repetitions:
        limitations.append("splits_do_not_prove_interval_compliance")
    return PlannedActualComparison(
        provider_activity_id=activity.provider_activity_id,
        planned_duration_seconds=planned.duration_seconds,
        actual_duration_seconds=actual_duration,
        duration_difference_seconds=(
            None
            if planned.duration_seconds is None
            else actual_duration - planned.duration_seconds
        ),
        planned_distance_meters=planned.distance_meters,
        actual_distance_meters=actual_distance,
        distance_difference_meters=(
            None
            if planned.distance_meters is None or actual_distance is None
            else actual_distance - planned.distance_meters
        ),
        planned_interval_repetitions=planned_repetitions,
        observed_split_count=split_count,
        limitations=tuple(limitations),
    )


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _float_or_none(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None
