from datetime import date

import pytest

from pace.database.models import PlannedSession, TrainingPlan
from pace.database.session import session_scope
from pace.planning.plan_models import (
    CoachAssessmentFact,
    PlanSessionFact,
    SessionTargetFact,
    TrainingPlanFact,
    WorkoutStepFact,
)
from pace.services.garmin_workout_export_service import GarminWorkoutExportService


TARGET = SessionTargetFact(
    kind="rpe",
    rpe_min=3,
    rpe_max=5,
    pace_seconds_per_km=None,
    power_watts=None,
    evidence_reference_id=None,
)


def _session_fact(session_id: int) -> PlanSessionFact:
    return PlanSessionFact(
        id=session_id,
        scheduled_date=date(2026, 9, 28),
        sport_type="run",
        purpose="Controlled intervals",
        distance_meters=None,
        duration_seconds=2_400,
        heart_rate_zone=None,
        target=TARGET,
        target_display="RPE 3–5",
        feedback_outcome=None,
        workout_steps=(
            WorkoutStepFact(
                kind="warmup",
                repetitions=1,
                distance_meters=None,
                duration_seconds=600,
                target=TARGET,
                recovery_distance_meters=None,
                recovery_duration_seconds=None,
                recovery_target=None,
                instruction="Easy warm-up",
            ),
            WorkoutStepFact(
                kind="interval",
                repetitions=4,
                distance_meters=400,
                duration_seconds=None,
                target=TARGET,
                recovery_distance_meters=None,
                recovery_duration_seconds=60,
                recovery_target=TARGET,
                instruction="Controlled, not maximal",
            ),
        ),
    )


class StubPlanService:
    def __init__(self, plan):
        self.plan = plan

    def list_plans(self):
        return (self.plan,)


class StubDestination:
    def __init__(self):
        self.uploads = 0
        self.schedules = 0
        self.pushes = 0

    def upload_planned_workout(self, workout, *, sport_type):
        self.uploads += 1
        assert sport_type == "run"
        payload = workout.to_dict()
        assert payload["workoutSegments"][0]["workoutSteps"][1]["numberOfIterations"] == 4
        return {"workoutId": 1234}

    def schedule_workout(self, workout_id, scheduled_date):
        self.schedules += 1
        assert workout_id == "1234"
        return {"calendarId": 5678}

    def push_workout_to_device(self, workout_id):
        self.pushes += 1
        return {"ok": True}

def test_export_is_explicit_structured_and_idempotent():
    with session_scope() as database:
        plan = TrainingPlan(
            status="accepted",
            contract_version=2,
            goal_mode="general",
            race_id=None,
            as_of_date=date(2026, 9, 25),
            block_start_date=date(2026, 9, 25),
            block_end_date=date(2026, 10, 25),
            detailed_start_date=date(2026, 9, 25),
            detailed_end_date=date(2026, 10, 8),
            block_outline=[],
            context_snapshot={},
            coach_assessment={},
        )
        database.add(plan)
        database.flush()
        stored = PlannedSession(
            plan_id=plan.id,
            scheduled_date=date(2026, 9, 28),
            sport_type="run",
            purpose="Controlled intervals",
            distance_meters=None,
            duration_seconds=2_400,
            intensity_type="rpe",
            intensity_zone=None,
            intensity_target="RPE 3–5",
            heart_rate_zone=None,
            target={},
            workout_steps=[],
        )
        database.add(stored)
        database.flush()
        plan_id = plan.id
        session_id = stored.id

    session = _session_fact(session_id)
    plan_fact = TrainingPlanFact(
        id=plan_id,
        parent_plan_id=None,
        status="accepted",
        contract_version=2,
        goal_mode="general",
        race_id=None,
        as_of_date=date(2026, 9, 25),
        block_start_date=date(2026, 9, 25),
        block_end_date=date(2026, 10, 25),
        detailed_start_date=date(2026, 9, 25),
        detailed_end_date=date(2026, 10, 8),
        block_outline=(),
        sessions=(session,),
        coach_assessment=CoachAssessmentFact((), (), (), "", (), ()),
    )
    destination = StubDestination()
    service = GarminWorkoutExportService(
        destination, plan_service=StubPlanService(plan_fact)
    )

    first = service.export(
        plan_id=plan_id, session_ids=(session_id,), push_to_device=False
    )
    second = service.export(
        plan_id=plan_id, session_ids=(session_id,), push_to_device=False
    )

    assert first[0].status == "scheduled"
    assert second[0].message.startswith("Existing Garmin workout")
    assert destination.uploads == 1
    assert destination.schedules == 1


def test_schedule_retry_reuses_uploaded_workout_instead_of_duplicating():
    with session_scope() as database:
        plan = TrainingPlan(
            status="accepted",
            contract_version=2,
            goal_mode="general",
            race_id=None,
            as_of_date=date(2026, 9, 25),
            block_start_date=date(2026, 9, 25),
            block_end_date=date(2026, 10, 25),
            detailed_start_date=date(2026, 9, 25),
            detailed_end_date=date(2026, 10, 8),
            block_outline=[],
            context_snapshot={},
            coach_assessment={},
        )
        database.add(plan)
        database.flush()
        stored = PlannedSession(
            plan_id=plan.id,
            scheduled_date=date(2026, 9, 28),
            sport_type="run",
            purpose="Controlled intervals",
            distance_meters=None,
            duration_seconds=2_400,
            intensity_type="rpe",
            intensity_zone=None,
            intensity_target="RPE 3–5",
            heart_rate_zone=None,
            target={},
            workout_steps=[],
        )
        database.add(stored)
        database.flush()
        plan_id, session_id = plan.id, stored.id

    session = _session_fact(session_id)
    plan_fact = TrainingPlanFact(
        id=plan_id,
        parent_plan_id=None,
        status="accepted",
        contract_version=2,
        goal_mode="general",
        race_id=None,
        as_of_date=date(2026, 9, 25),
        block_start_date=date(2026, 9, 25),
        block_end_date=date(2026, 10, 25),
        detailed_start_date=date(2026, 9, 25),
        detailed_end_date=date(2026, 10, 8),
        block_outline=(),
        sessions=(session,),
        coach_assessment=CoachAssessmentFact((), (), (), "", (), ()),
    )

    class FailsOnce(StubDestination):
        def schedule_workout(self, workout_id, scheduled_date):
            self.schedules += 1
            if self.schedules == 1:
                raise RuntimeError("temporary Garmin failure")
            return {"calendarId": 5678}

    destination = FailsOnce()
    service = GarminWorkoutExportService(
        destination, plan_service=StubPlanService(plan_fact)
    )
    with pytest.raises(RuntimeError, match="temporary Garmin failure"):
        service.export(
            plan_id=plan_id, session_ids=(session_id,), push_to_device=False
        )

    result = service.export(
        plan_id=plan_id, session_ids=(session_id,), push_to_device=False
    )

    assert result[0].status == "scheduled"
    assert destination.uploads == 1
    assert destination.schedules == 2
