"""Convert Pace's structured session contract to typed Garmin workouts."""

from __future__ import annotations

from typing import Any

from garminconnect.workout import (
    CyclingWorkout,
    ExecutableStep,
    RunningWorkout,
    SportType,
    TargetType,
    WorkoutSegment,
    create_cooldown_step,
    create_distance_interval_step,
    create_interval_step,
    create_recovery_step,
    create_repeat_group,
    create_warmup_step,
)

from pace.planning.plan_models import PlanSessionFact, WorkoutStepFact


def pace_session_to_garmin_workout(
    session: PlanSessionFact,
) -> RunningWorkout | CyclingWorkout:
    """Build a typed workout; RPE remains an instruction, never a fake target."""

    if session.sport_type not in {"run", "ride"}:
        raise ValueError("Only running and cycling sessions can be exported to Garmin.")
    sport_type = _sport_type(session.sport_type)
    steps: list[Any] = []
    if session.workout_steps:
        for order, item in enumerate(session.workout_steps, start=1):
            steps.append(_workout_step(item, order, session.heart_rate_zone))
    else:
        steps.append(
            _executable_step(
                kind="steady",
                order=1,
                duration_seconds=session.duration_seconds,
                distance_meters=session.distance_meters,
                target=_heart_rate_target(session.heart_rate_zone),
                instruction=session.purpose,
            )
        )

    estimated = session.duration_seconds or _estimated_duration(session.workout_steps)
    workout_type = RunningWorkout if session.sport_type == "run" else CyclingWorkout
    return workout_type(
        workoutName=f"Pace · {session.purpose}"[:80],
        estimatedDurationInSecs=max(int(estimated or 1), 1),
        description=(
            f"Pace session {session.id} on {session.scheduled_date.isoformat()}. "
            f"{session.target_display}"
        )[:500],
        workoutSegments=[
            WorkoutSegment(
                segmentOrder=1,
                sportType=sport_type,
                workoutSteps=steps,
            )
        ],
    )


def _workout_step(
    step: WorkoutStepFact, order: int, session_hr_zone: int | None
):
    target = _heart_rate_target(session_hr_zone)
    work = _executable_step(
        kind=step.kind,
        order=1 if step.repetitions > 1 else order,
        duration_seconds=step.duration_seconds,
        distance_meters=step.distance_meters,
        target=target,
        instruction=step.instruction,
    )
    if step.repetitions <= 1:
        return work

    repeated: list[Any] = [work]
    if step.recovery_duration_seconds or step.recovery_distance_meters:
        repeated.append(
            _executable_step(
                kind="recovery",
                order=2,
                duration_seconds=step.recovery_duration_seconds,
                distance_meters=step.recovery_distance_meters,
                target=None,
                instruction="Recovery",
            )
        )
    return create_repeat_group(step.repetitions, repeated, order)


def _executable_step(
    *,
    kind: str,
    order: int,
    duration_seconds: int | None,
    distance_meters: float | None,
    target: dict[str, Any] | None,
    instruction: str,
) -> ExecutableStep:
    if duration_seconds is None and distance_meters is None:
        raise ValueError("Every exported workout block needs a duration or distance.")
    if kind == "warmup" and duration_seconds is not None:
        result = create_warmup_step(duration_seconds, order, target)
    elif kind == "cooldown" and duration_seconds is not None:
        result = create_cooldown_step(duration_seconds, order, target)
    elif kind == "recovery" and duration_seconds is not None:
        result = create_recovery_step(duration_seconds, order, target)
    elif distance_meters is not None:
        result = create_distance_interval_step(distance_meters, order, target)
    else:
        result = create_interval_step(duration_seconds or 1, order, target)
    result.description = instruction[:200]
    return result


def _heart_rate_target(zone: int | None) -> dict[str, Any] | None:
    if zone is None:
        return None
    return {
        "workoutTargetTypeId": TargetType.HEART_RATE_ZONE,
        "workoutTargetTypeKey": "heart.rate.zone",
        "displayOrder": 4,
        "zoneNumber": zone,
    }


def _sport_type(sport_type: str) -> dict[str, Any]:
    if sport_type == "run":
        return {
            "sportTypeId": SportType.RUNNING,
            "sportTypeKey": "running",
            "displayOrder": 1,
        }
    return {
        "sportTypeId": SportType.CYCLING,
        "sportTypeKey": "cycling",
        "displayOrder": 2,
    }


def _estimated_duration(steps: tuple[WorkoutStepFact, ...]) -> int:
    total = 0
    for step in steps:
        work = step.duration_seconds or 0
        recovery = step.recovery_duration_seconds or 0
        total += step.repetitions * (work + recovery)
    return total
