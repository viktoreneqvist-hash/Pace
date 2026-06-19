from sqlalchemy import select
from sqlalchemy.orm import Session

from running_agent.models.activity import Activity


def save_activity(session: Session, activity: Activity) -> Activity:
    session.add(activity)
    session.commit()
    session.refresh(activity)

    return activity


def list_activities(session: Session) -> list[Activity]:
    statement = select(Activity)
    activities = session.scalars(statement).all()

    return list(activities)

def get_activity_by_external_id(session: Session, external_id: str) -> Activity | None:
    statement = select(Activity).where(Activity.external_id == external_id)
    return session.scalars(statement).first()