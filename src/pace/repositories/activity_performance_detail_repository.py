"""Persistence operations for minimal normalized activity-detail facts."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from pace.database.models import ActivityPerformanceDetail


DETAIL_UPDATE_FIELDS = (
    "duration_seconds",
    "distance_meters",
    "average_heart_rate",
    "maximum_heart_rate",
    "average_speed_mps",
    "average_cadence",
    "average_power",
    "splits",
)


def get_detail_for_activity(
    session: Session, *, activity_id: int
) -> ActivityPerformanceDetail | None:
    statement = select(ActivityPerformanceDetail).where(
        ActivityPerformanceDetail.activity_id == activity_id
    )
    return session.scalar(statement)


def get_details_for_activities(
    session: Session, *, activity_ids: list[int]
) -> dict[int, ActivityPerformanceDetail]:
    if not activity_ids:
        return {}
    statement = select(ActivityPerformanceDetail).where(
        ActivityPerformanceDetail.activity_id.in_(activity_ids)
    )
    return {detail.activity_id: detail for detail in session.scalars(statement)}


def upsert_activity_performance_detail(
    session: Session,
    detail: ActivityPerformanceDetail,
) -> tuple[ActivityPerformanceDetail, bool, bool]:
    """Upsert details so an identical retry has zero changed records."""

    existing = get_detail_for_activity(session, activity_id=detail.activity_id)
    if existing is None:
        session.add(detail)
        session.flush()
        return detail, True, False

    changed = any(
        getattr(existing, field_name) != getattr(detail, field_name)
        for field_name in DETAIL_UPDATE_FIELDS
    )
    if changed:
        for field_name in DETAIL_UPDATE_FIELDS:
            setattr(existing, field_name, getattr(detail, field_name))
        session.flush()
    return existing, False, changed
