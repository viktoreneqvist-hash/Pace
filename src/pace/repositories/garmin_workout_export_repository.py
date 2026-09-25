"""Persistence operations for idempotent Garmin workout exports."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from pace.database.models import GarminWorkoutExport


def get_export_for_session(
    session: Session, *, planned_session_id: int
) -> GarminWorkoutExport | None:
    return session.scalar(
        select(GarminWorkoutExport).where(
            GarminWorkoutExport.planned_session_id == planned_session_id
        )
    )


def get_exports_for_sessions(
    session: Session, *, planned_session_ids: list[int]
) -> dict[int, GarminWorkoutExport]:
    if not planned_session_ids:
        return {}
    statement = select(GarminWorkoutExport).where(
        GarminWorkoutExport.planned_session_id.in_(planned_session_ids)
    )
    return {
        item.planned_session_id: item for item in session.scalars(statement)
    }


def create_workout_export(
    session: Session, export: GarminWorkoutExport
) -> GarminWorkoutExport:
    session.add(export)
    session.flush()
    return export


def mark_export_pushed(export: GarminWorkoutExport) -> GarminWorkoutExport:
    export.pushed_to_device = True
    export.status = "scheduled_and_pushed"
    return export


def mark_export_scheduled(
    export: GarminWorkoutExport, *, garmin_schedule_id: str | None
) -> GarminWorkoutExport:
    export.garmin_schedule_id = garmin_schedule_id
    export.status = "scheduled"
    return export
