"""Explicit persistence operations for immutable plan versions and outcomes."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from pace.database.models import PlannedSession, SessionFeedback, TrainingPlan


def create_training_plan(session: Session, plan: TrainingPlan) -> TrainingPlan:
    session.add(plan)
    session.flush()
    return plan


def get_training_plan(session: Session, *, plan_id: int) -> TrainingPlan | None:
    return session.get(TrainingPlan, plan_id)


def list_training_plans(session: Session) -> list[TrainingPlan]:
    return list(session.scalars(select(TrainingPlan).order_by(TrainingPlan.id.desc())))


def create_planned_session(session: Session, planned_session: PlannedSession) -> PlannedSession:
    session.add(planned_session)
    session.flush()
    return planned_session


def get_sessions_for_plan(session: Session, *, plan_id: int) -> list[PlannedSession]:
    statement = select(PlannedSession).where(PlannedSession.plan_id == plan_id).order_by(
        PlannedSession.scheduled_date, PlannedSession.id
    )
    return list(session.scalars(statement))


def get_planned_session(session: Session, *, session_id: int) -> PlannedSession | None:
    return session.get(PlannedSession, session_id)


def get_feedback_for_sessions(
    session: Session, *, session_ids: list[int]
) -> dict[int, SessionFeedback]:
    if not session_ids:
        return {}
    statement = select(SessionFeedback).where(
        SessionFeedback.planned_session_id.in_(session_ids)
    )
    return {feedback.planned_session_id: feedback for feedback in session.scalars(statement)}


def upsert_session_feedback(
    session: Session,
    *,
    planned_session_id: int,
    outcome: str,
    note: str | None,
    share_note_with_ai: bool,
) -> SessionFeedback:
    feedback = session.scalar(
        select(SessionFeedback).where(
            SessionFeedback.planned_session_id == planned_session_id
        )
    )
    if feedback is None:
        feedback = SessionFeedback(
            planned_session_id=planned_session_id,
            outcome=outcome,
            note=note,
            share_note_with_ai=share_note_with_ai,
        )
        session.add(feedback)
    else:
        feedback.outcome = outcome
        feedback.note = note
        feedback.share_note_with_ai = share_note_with_ai
    session.flush()
    return feedback
