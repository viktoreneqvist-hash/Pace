"""Explicit acceptance and expiry of model-proposed coaching principles."""

from datetime import date, timedelta

from sqlalchemy import select

from pace.database.models import AthleteCoachingPrinciple
from pace.database.session import session_scope
from pace.repositories.training_plan_repository import get_training_plan


class CoachingPrincipleService:
    def accept_from_plan(self, *, plan_id: int, principle_index: int, as_of_date: date) -> AthleteCoachingPrinciple:
        with session_scope() as session:
            plan = get_training_plan(session, plan_id=plan_id)
            if plan is None:
                raise ValueError(f"No plan exists with id {plan_id}.")
            principles = plan.coach_assessment.get("coaching_principles", [])
            if not isinstance(principles, list) or not 0 <= principle_index < len(principles):
                raise ValueError("No coach principle exists at that index.")
            statement = principles[principle_index]
            if not isinstance(statement, str) or not statement.strip():
                raise ValueError("The selected coach principle is invalid.")
            principle = AthleteCoachingPrinciple(
                statement=statement.strip(), source_plan_id=plan_id, status="active",
                review_due_date=as_of_date + timedelta(days=84),
            )
            session.add(principle)
            session.flush()
            return principle

    def list_active(self, *, as_of_date: date):
        with session_scope() as session:
            rows = list(session.scalars(select(AthleteCoachingPrinciple).where(AthleteCoachingPrinciple.status == "active").order_by(AthleteCoachingPrinciple.id)))
            return tuple((item, item.review_due_date < as_of_date) for item in rows)

    def archive(self, *, principle_id: int) -> None:
        with session_scope() as session:
            item = session.get(AthleteCoachingPrinciple, principle_id)
            if item is None or item.status != "active":
                raise ValueError("No active coaching principle exists with that id.")
            item.status = "archived"
