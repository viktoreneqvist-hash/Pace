"""Explicit, idempotent export of accepted Pace sessions to Garmin."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.orm import Session

from pace.database.models import GarminWorkoutExport
from pace.database.session import SessionFactory
from pace.integrations.garmin.workouts import pace_session_to_garmin_workout
from pace.planning.plan_models import PlanSessionFact
from pace.repositories.garmin_workout_export_repository import (
    create_workout_export,
    get_export_for_session,
    get_exports_for_sessions,
    mark_export_pushed,
    mark_export_scheduled,
)
from pace.services.training_plan_service import TrainingPlanService


class GarminWorkoutDestination(Protocol):
    def upload_planned_workout(
        self, workout: Any, *, sport_type: str
    ) -> dict[str, Any]: ...

    def schedule_workout(
        self, workout_id: str, scheduled_date
    ) -> dict[str, Any]: ...

    def push_workout_to_device(self, workout_id: str) -> dict[str, Any]: ...

@dataclass(frozen=True, slots=True)
class WorkoutExportFact:
    session_id: int
    status: str
    garmin_workout_id: str | None
    scheduled_date: str
    pushed_to_device: bool
    message: str


class GarminWorkoutExportService:
    """Keep external writes explicit and duplicate-safe."""

    def __init__(
        self,
        destination: GarminWorkoutDestination | None = None,
        *,
        plan_service: TrainingPlanService | None = None,
        session_factory: Callable[[], Session] = SessionFactory,
    ) -> None:
        self._destination = destination
        self._plan_service = plan_service or TrainingPlanService()
        self._session_factory = session_factory

    def get_status(self, *, plan_id: int) -> tuple[WorkoutExportFact, ...]:
        plan = self._accepted_plan(plan_id)
        with self._session_factory() as database:
            exports = get_exports_for_sessions(
                database, planned_session_ids=[item.id for item in plan.sessions]
            )
        return tuple(
            _fact(item, exports.get(item.id)) for item in plan.sessions
        )

    def export(
        self,
        *,
        plan_id: int,
        session_ids: tuple[int, ...],
        push_to_device: bool,
    ) -> tuple[WorkoutExportFact, ...]:
        if self._destination is None:
            raise RuntimeError("A Garmin workout destination is required for export.")
        plan = self._accepted_plan(plan_id)
        selected = [item for item in plan.sessions if item.id in set(session_ids)]
        if not selected or len(selected) != len(set(session_ids)):
            raise ValueError("Every selected session must belong to the accepted plan.")

        results: list[WorkoutExportFact] = []
        for session in selected:
            results.append(self._export_one(session, push_to_device=push_to_device))
        return tuple(results)

    def _export_one(
        self, session: PlanSessionFact, *, push_to_device: bool
    ) -> WorkoutExportFact:
        with self._session_factory() as database:
            existing = get_export_for_session(
                database, planned_session_id=session.id
            )
        if existing is not None:
            if existing.status == "uploaded":
                scheduled = self._destination.schedule_workout(
                    existing.garmin_workout_id, session.scheduled_date
                )
                schedule_id = _response_id(
                    scheduled,
                    "calendarId",
                    "scheduleId",
                    "scheduledWorkoutId",
                    "id",
                )
                with self._session_factory.begin() as database:
                    stored = get_export_for_session(
                        database, planned_session_id=session.id
                    )
                    if stored is not None:
                        mark_export_scheduled(
                            stored, garmin_schedule_id=schedule_id
                        )
                existing.status = "scheduled"
                existing.garmin_schedule_id = schedule_id
            if push_to_device and not existing.pushed_to_device:
                self._destination.push_workout_to_device(existing.garmin_workout_id)
                with self._session_factory.begin() as database:
                    stored = get_export_for_session(
                        database, planned_session_id=session.id
                    )
                    if stored is not None:
                        mark_export_pushed(stored)
                existing.pushed_to_device = True
                existing.status = "scheduled_and_pushed"
            return _fact(
                session,
                existing,
                "Existing Garmin workout was reused; no duplicate was created.",
            )

        workout = pace_session_to_garmin_workout(session)
        fingerprint = hashlib.sha256(
            json.dumps(workout.to_dict(), sort_keys=True).encode("utf-8")
        ).hexdigest()
        upload = self._destination.upload_planned_workout(
            workout, sport_type=session.sport_type
        )
        workout_id = _response_id(upload, "workoutId", "workout_id", "id")
        if workout_id is None:
            raise ValueError("Garmin uploaded the workout but returned no workout id.")
        with self._session_factory.begin() as database:
            stored = create_workout_export(
                database,
                GarminWorkoutExport(
                    planned_session_id=session.id,
                    garmin_workout_id=workout_id,
                    garmin_schedule_id=None,
                    scheduled_date=session.scheduled_date,
                    workout_fingerprint=fingerprint,
                    status="uploaded",
                    pushed_to_device=False,
                ),
            )

        scheduled = self._destination.schedule_workout(
            workout_id, session.scheduled_date
        )
        schedule_id = _response_id(
            scheduled, "calendarId", "scheduleId", "scheduledWorkoutId", "id"
        )

        with self._session_factory.begin() as database:
            persisted = get_export_for_session(
                database, planned_session_id=session.id
            )
            if persisted is None:
                raise RuntimeError("The local Garmin workout mapping was not found.")
            mark_export_scheduled(persisted, garmin_schedule_id=schedule_id)
        stored.status = "scheduled"
        stored.garmin_schedule_id = schedule_id

        if push_to_device:
            self._destination.push_workout_to_device(workout_id)
            with self._session_factory.begin() as database:
                persisted = get_export_for_session(
                    database, planned_session_id=session.id
                )
                if persisted is not None:
                    mark_export_pushed(persisted)
            stored.pushed_to_device = True
            stored.status = "scheduled_and_pushed"
        return _fact(session, stored, "Workout created and scheduled in Garmin.")

    def _accepted_plan(self, plan_id: int):
        plan = next(
            (item for item in self._plan_service.list_plans() if item.id == plan_id),
            None,
        )
        if plan is None or plan.status != "accepted":
            raise ValueError("Garmin export requires an accepted Pace plan.")
        return plan


def _fact(
    session: PlanSessionFact,
    export: GarminWorkoutExport | None,
    message: str | None = None,
) -> WorkoutExportFact:
    return WorkoutExportFact(
        session_id=session.id,
        status="not_exported" if export is None else export.status,
        garmin_workout_id=None if export is None else export.garmin_workout_id,
        scheduled_date=session.scheduled_date.isoformat(),
        pushed_to_device=False if export is None else export.pushed_to_device,
        message=message or (
            "Not exported to Garmin."
            if export is None
            else (
                "Uploaded to Garmin; calendar scheduling must be retried."
                if export.status == "uploaded"
                else "Scheduled in Garmin."
            )
        ),
    )


def _response_id(payload: Any, *keys: str) -> str | None:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if value is not None and str(value).isdigit():
                return str(value)
        for value in payload.values():
            found = _response_id(value, *keys)
            if found is not None:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _response_id(value, *keys)
            if found is not None:
                return found
    return None
