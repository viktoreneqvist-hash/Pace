"""Make a read-only comparison of a planned workout and same-day Garmin facts."""

from pace.database.session import session_scope
from pace.repositories.activity_repository import get_activities_in_date_range
from pace.repositories.training_plan_repository import (
    get_feedback_for_sessions,
    get_planned_session,
    get_training_plan,
)
from pace.services.training_plan_service import _workout_steps_fact
from pace.timezones import athlete_local_date
from pace.workouts.models import MatchingActivityFact, WorkoutEvaluation


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
            matches = tuple(
                MatchingActivityFact(
                    provider_activity_id=activity.provider_activity_id,
                    activity_date=athlete_local_date(activity.start_time),
                    distance_meters=activity.distance_meters,
                    duration_seconds=activity.duration_seconds,
                )
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
                planned_steps=_workout_steps_fact(planned),
                feedback_outcome=None if feedback is None else feedback.outcome,
                feedback_perceived_exertion=(
                    None if feedback is None else feedback.perceived_exertion
                ),
                feedback_reason_code=None if feedback is None else feedback.reason_code,
                matching_activities=matches,
                limitations=tuple(limitations),
            )
