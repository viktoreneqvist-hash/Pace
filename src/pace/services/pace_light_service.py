"""Build a bounded, privacy-minimized snapshot for the hosted Pace Light mirror."""

from datetime import date, datetime, timedelta, timezone
import json
from typing import Any
from urllib.request import Request, urlopen

from pace.database.session import session_scope
from pace.repositories.activity_repository import get_all_activities
from pace.services.training_plan_service import TrainingPlanService


PACE_LIGHT_SCHEMA_VERSION = 1
MAX_RECENT_ACTIVITIES = 84


class PaceLightService:
    """Select read-only facts locally and upload one replaceable snapshot."""

    def build_snapshot(self, *, as_of_date: date) -> dict[str, Any]:
        with session_scope() as session:
            activities = get_all_activities(session)
        activities = _select_recent_activities(activities, as_of_date=as_of_date)
        plans = TrainingPlanService().list_plans()
        active_plan = next(
            (
                plan
                for plan in reversed(plans)
                if plan.status == "accepted"
                and plan.block_start_date <= as_of_date <= plan.block_end_date
            ),
            None,
        )
        return {
            "schema_version": PACE_LIGHT_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "as_of_date": as_of_date.isoformat(),
            "recent_activities": [
                {
                    "sport_type": item.sport_type,
                    "start_time": item.start_time.isoformat(),
                    "duration_seconds": item.duration_seconds,
                    "distance_meters": item.distance_meters,
                    "average_heart_rate": item.average_heart_rate,
                }
                for item in activities
            ],
            "active_plan": None if active_plan is None else _serialize_plan(active_plan),
        }

    def upload_snapshot(
        self,
        *,
        snapshot: dict[str, Any],
        site_url: str,
        service_token: str,
        timeout_seconds: int = 20,
    ) -> None:
        endpoint = f"{site_url.rstrip('/')}/api/snapshot"
        request = Request(
            endpoint,
            data=json.dumps(snapshot, separators=(",", ":")).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "OAI-Sites-Authorization": f"Bearer {service_token}",
            },
            method="POST",
        )
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            if response.status != 200:
                raise RuntimeError(f"Pace Light rejected the snapshot (HTTP {response.status}).")


def _serialize_plan(plan) -> dict[str, Any]:
    return {
        "detailed_start_date": plan.detailed_start_date.isoformat(),
        "detailed_end_date": plan.detailed_end_date.isoformat(),
        "goal_mode": plan.goal_mode,
        "sessions": [
            {
                "scheduled_date": session.scheduled_date.isoformat(),
                "sport_type": session.sport_type,
                "purpose": session.purpose,
                "duration_seconds": session.duration_seconds,
                "distance_meters": session.distance_meters,
                "target_display": session.target_display,
                "workout_steps": [
                    {
                        "kind": step.kind,
                        "repetitions": step.repetitions,
                        "duration_seconds": step.duration_seconds,
                        "distance_meters": step.distance_meters,
                        "target_display": _target_display(step.target),
                        "recovery_display": _recovery_display(step),
                        "instruction": step.instruction,
                    }
                    for step in session.workout_steps
                ],
            }
            for session in plan.sessions
            if session.scheduled_date >= plan.as_of_date
        ],
    }


def _select_recent_activities(activities, *, as_of_date: date):
    eligible = [
        item
        for item in activities
        if item.sport_type in {"run", "ride"}
        and item.start_time.date() <= as_of_date
    ]
    if not eligible:
        return []
    window_end = eligible[-1].start_time.date()
    window_start = window_end - timedelta(days=27)
    return [
        item for item in eligible if window_start <= item.start_time.date() <= window_end
    ][-MAX_RECENT_ACTIVITIES:]


def _target_display(target) -> str:
    if target.kind == "rpe":
        return f"RPE {target.rpe_min}–{target.rpe_max}"
    if target.kind == "pace":
        return f"{target.pace_seconds_per_km} sec/km"
    if target.kind == "power":
        return f"{target.power_watts} W"
    return "No additional target"


def _recovery_display(step) -> str | None:
    if step.recovery_distance_meters is None and step.recovery_duration_seconds is None:
        return None
    dose = (
        f"{step.recovery_distance_meters / 1000:g} km"
        if step.recovery_distance_meters is not None
        else f"{step.recovery_duration_seconds // 60:g} min"
    )
    return dose if step.recovery_target is None else f"{dose} · {_target_display(step.recovery_target)}"
