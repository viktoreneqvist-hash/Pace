"""Normalized, same-origin presentation API for the Pace React interface."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from pace.config.settings import resolve_openai_api_key, settings
from pace.integrations.garmin.client import GARMIN_TOKEN_FILENAME
from pace.presentation.weekly_review import load_weekly_review_snapshot
from pace.services.race_service import RaceInput, resolved_taper
from pace.timezones import athlete_local_date


class RaceMutation(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    sport: str
    date: date
    distance_km: float = Field(gt=0, le=1_000)
    priority: str
    desired_time_seconds: int | None = Field(default=None, gt=0)
    taper_override: str | None = None


class VolumeExceptionApproval(BaseModel):
    plan_id: int = Field(gt=0)


def install_api_v1(
    app: FastAPI,
    *,
    services: Any,
    session_value: Callable[[Request, str], str],
    require_csrf: Callable[[Request], None],
) -> None:
    """Install a thin DTO layer without duplicating Pace service logic."""

    router = APIRouter(prefix="/api/v1")

    @router.get("/bootstrap")
    def bootstrap(request: Request) -> dict[str, object]:
        return {
            "csrfToken": session_value(request, "csrf_token"),
            "prototype": False,
            "today": services.today().isoformat(),
            "productLanguage": "en",
        }

    @router.get("/today")
    def today() -> dict[str, object]:
        as_of = services.today()
        plan = _active_plan(services.plan_service.list_plans(), as_of)
        checkpoint = services.checkpoint_service.get_checkpoint(as_of_date=as_of)
        analysis = services.analysis_service.get_analysis(end_date=as_of)
        dashboard = services.dashboard_service.get_dashboard_data(end_date=as_of)
        next_session = _next_session(plan, as_of)
        race = _race_for_plan(services, plan, as_of)
        freshness = _freshness(dashboard.state, as_of)
        facts = _today_facts(analysis, dashboard.state)
        return {
            "athleteName": "Athlete",
            "today": as_of.isoformat(),
            "session": None if next_session is None else _session(next_session),
            "rationale": _today_rationale(plan, next_session),
            "facts": facts,
            "dataQuality": _data_quality(dashboard.state, as_of),
            "goal": _goal(plan, race, as_of),
            "revisionDue": getattr(checkpoint, "status", None) == "revision_due",
            "actionNeeded": _action_needed(freshness, plan, next_session),
        }

    @router.get("/plans/active")
    def active_plan() -> dict[str, object] | None:
        as_of = services.today()
        plan = _active_plan(services.plan_service.list_plans(), as_of)
        if plan is None:
            return None
        checkpoint = services.checkpoint_service.get_checkpoint(as_of_date=as_of)
        race = _race_for_plan(services, plan, as_of)
        return _plan(plan, race, checkpoint, as_of)

    @router.get("/plans/history")
    def plan_history() -> list[dict[str, object]]:
        result = []
        for plan in services.plan_service.list_plans():
            result.append(
                {
                    "id": str(plan.id),
                    "version": int(getattr(plan, "contract_version", 1)),
                    "acceptedAt": getattr(
                        plan, "as_of_date", services.today()
                    ).isoformat(),
                    "mode": plan.goal_mode,
                    "windowLabel": (
                        f"{plan.detailed_start_date.isoformat()} – "
                        f"{plan.detailed_end_date.isoformat()}"
                    ),
                    "sessionCount": len(plan.sessions),
                    "note": f"Stored plan version · {plan.status}",
                }
            )
        return result

    @router.get("/plans/pending-volume-exception")
    def pending_volume_exception() -> dict[str, object] | None:
        plan = next(
            (
                item
                for item in services.plan_service.list_plans()
                if item.status == "volume_exception_pending"
            ),
            None,
        )
        if plan is None or plan.volume_exception is None:
            return None
        race = _race_for_plan(services, plan, services.today())
        return {
            "planId": str(plan.id),
            "raceName": "Selected race" if race is None else race.name,
            "rationale": plan.volume_exception.rationale,
            "weeks": [
                {
                    "weekStart": week.week_start.isoformat(),
                    "weekEnd": week.week_end.isoformat(),
                    "breaches": [
                        {
                            "metric": breach.metric,
                            "ceiling": breach.ceiling,
                            "proposed": breach.proposed,
                            "unit": breach.unit,
                        }
                        for breach in week.breaches
                    ],
                }
                for week in plan.volume_exception.weeks
            ],
        }

    @router.post("/plans/volume-exception/approve")
    def approve_volume_exception(
        request: Request, payload: VolumeExceptionApproval
    ) -> dict[str, object]:
        require_csrf(request)
        try:
            plan = services.plan_service.approve_volume_exception(
                plan_id=payload.plan_id
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"status": "accepted", "planId": str(plan.id)}

    @router.get("/dashboard")
    def dashboard(days: int = 28) -> dict[str, object]:
        if days not in {28, 84}:
            raise HTTPException(
                status_code=422, detail="Dashboard days must be 28 or 84."
            )
        as_of = services.today()
        data = services.dashboard_service.get_dashboard_data(end_date=as_of, days=days)
        return _dashboard(data, days, as_of)

    @router.get("/weekly-reviews/latest")
    def weekly_review() -> dict[str, object]:
        snapshot = load_weekly_review_snapshot(
            reports_directory=services.reports_directory
        )
        if snapshot is None:
            return {"status": "absent", "snapshot": None, "history": []}
        return {
            "status": "saved",
            "snapshot": {
                "id": snapshot.end_date.isoformat(),
                "weekLabel": f"Week ending {snapshot.end_date.isoformat()}",
                "generatedAt": f"{snapshot.end_date.isoformat()}T12:00:00Z",
                "summary": [snapshot.summary],
                "paceFacts": _text_facts("observation", snapshot.observations),
                "garminFacts": [],
                "assessment": list(snapshot.coach_assessment),
                "recommendations": list(snapshot.recommendations),
                "uncertainties": list(snapshot.uncertainties),
                "knowledge": [],
                "immutableNote": (
                    "This explicit snapshot is not regenerated when the page opens."
                ),
            },
            "history": [
                {
                    "id": snapshot.end_date.isoformat(),
                    "weekLabel": f"Week ending {snapshot.end_date.isoformat()}",
                    "generatedAt": f"{snapshot.end_date.isoformat()}T12:00:00Z",
                }
            ],
        }

    @router.get("/races")
    def races() -> dict[str, object]:
        as_of = services.today()
        items = _all_races(services, as_of)
        active = _active_plan(services.plan_service.list_plans(), as_of)
        active_race_id = None if active is None else active.race_id
        return {
            "races": [_race(item, active_race_id) for item in items],
            "activeTargetId": None if active_race_id is None else str(active_race_id),
            "note": (
                "Registering a race records an option. It becomes a target only "
                "when you explicitly create a plan for it."
            ),
        }

    @router.post("/races")
    def add_race(request: Request, payload: RaceMutation) -> dict[str, object]:
        require_csrf(request)
        try:
            race = services.race_service.add_race(
                RaceInput(
                    name=payload.name,
                    sport_type=_internal_sport(payload.sport),
                    race_date=payload.date,
                    distance_meters=payload.distance_km * 1_000,
                    priority=payload.priority,
                    desired_time_seconds=payload.desired_time_seconds,
                    taper_override=payload.taper_override,
                )
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"status": "saved", "message": "Race saved.", "raceId": race.id}

    @router.put("/races/{race_id}")
    def update_race(
        request: Request, race_id: int, payload: RaceMutation
    ) -> dict[str, object]:
        require_csrf(request)
        try:
            services.race_service.update_race(
                race_id=race_id,
                name=payload.name,
                sport_type=_internal_sport(payload.sport),
                race_date=payload.date,
                distance_meters=payload.distance_km * 1_000,
                priority=payload.priority,
                desired_time_seconds=payload.desired_time_seconds,
                clear_desired_time=payload.desired_time_seconds is None,
                taper_override=payload.taper_override or "default",
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"status": "saved", "message": "Race updated."}

    @router.post("/races/{race_id}/cancel")
    def cancel_race(request: Request, race_id: int) -> dict[str, object]:
        require_csrf(request)
        try:
            services.race_service.cancel_race(
                race_id=race_id, as_of_date=services.today()
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"status": "saved", "message": "Race cancelled."}

    @router.get("/settings")
    def settings_view() -> dict[str, object]:
        preference = services.preference_service.get_preference()
        zones = services.zone_service.get_profile(sport_type="ride")
        return {
            "sportRole": ("balanced" if preference is None else preference.sport_role),
            "ambition": (
                "balanced" if preference is None else preference.coaching_ambition
            ),
            "availability": _availability(preference),
            "volumeBoundaries": {
                "runningKmPerWeek": (
                    None
                    if preference is None
                    else getattr(preference, "base_running_distance_ceiling_km", None)
                ),
                "cyclingHoursPerWeek": (
                    None
                    if preference is None
                    else getattr(
                        preference, "base_cycling_duration_ceiling_hours", None
                    )
                ),
                "totalHoursPerWeek": (
                    None
                    if preference is None
                    else getattr(preference, "base_total_duration_ceiling_hours", None)
                ),
            },
            "cyclingZones": _zones(zones),
            "zonesConfirmed": zones is not None,
            "connections": [
                {
                    "id": "garmin",
                    "label": "Garmin",
                    "state": (
                        "connected"
                        if (settings.garmin_token_dir / GARMIN_TOKEN_FILENAME).is_file()
                        else "not_connected"
                    ),
                    "detail": "Garmin session is stored locally with owner-only permissions.",
                },
                {
                    "id": "openai",
                    "label": "OpenAI",
                    "state": (
                        "connected"
                        if resolve_openai_api_key(settings)
                        else "not_connected"
                    ),
                    "detail": "The API key remains in the local Pace secrets file.",
                },
            ],
            "note": "Settings are athlete intent, not evidence of training capacity.",
        }

    @router.get("/sessions/{session_id}")
    def session_detail(session_id: int) -> dict[str, object] | None:
        plan, session = _find_session(services.plan_service.list_plans(), session_id)
        if plan is None or session is None:
            return None
        return {
            "session": _plan_session(session),
            "planLabel": f"Plan {plan.id} · {plan.goal_mode}",
            "paceFacts": [
                _fact(
                    "planned-date", "Planned date", session.scheduled_date.isoformat()
                ),
                _fact("planned-target", "Planned target", session.target_display),
            ],
            "garminFacts": [],
            "garminNote": (
                "A matched Garmin activity confirms that activity happened. It does "
                "not prove that prescribed interval targets were met."
            ),
            "feedbackNote": "Explicit athlete feedback is the durable outcome.",
        }

    app.include_router(router)


def _active_plan(plans: Any, as_of: date) -> Any | None:
    return next(
        (
            plan
            for plan in plans
            if plan.status == "accepted"
            and plan.block_start_date <= as_of <= plan.block_end_date
        ),
        None,
    )


def _next_session(plan: Any | None, as_of: date) -> Any | None:
    if plan is None:
        return None
    return next((item for item in plan.sessions if item.scheduled_date >= as_of), None)


def _find_session(plans: Any, session_id: int) -> tuple[Any | None, Any | None]:
    for plan in plans:
        for session in plan.sessions:
            if session.id == session_id:
                return plan, session
    return None, None


def _all_races(services: Any, as_of: date) -> list[Any]:
    list_races = getattr(services.race_service, "list_races", None)
    if callable(list_races):
        return list_races(as_of_date=as_of, include_past=True, include_cancelled=True)
    return list(services.race_service.list_upcoming_races(as_of_date=as_of))


def _race_for_plan(services: Any, plan: Any | None, as_of: date) -> Any | None:
    race_id = None if plan is None else getattr(plan, "race_id", None)
    if race_id is None:
        return None
    return next(
        (item for item in _all_races(services, as_of) if item.id == race_id), None
    )


def _sport(value: str) -> str:
    return "running" if value == "run" else "cycling"


def _internal_sport(value: str) -> str:
    return {"running": "run", "cycling": "ride"}.get(value, value)


def _session(item: Any) -> dict[str, object]:
    return {
        "id": str(item.id),
        "date": item.scheduled_date.isoformat(),
        "sport": _sport(item.sport_type),
        "title": item.purpose,
        "purpose": item.purpose,
        "scope": _scope(item.distance_meters, item.duration_seconds),
        "mainTarget": item.target_display or "No separate intensity target",
        "blocks": _blocks(item),
        **_feedback(item),
    }


def _plan_session(item: Any) -> dict[str, object]:
    payload = _session(item)
    payload.update(
        {
            "rationale": item.purpose,
            "assessment": [],
            "uncertainty": [],
        }
    )
    return payload


def _feedback(item: Any) -> dict[str, object]:
    outcome = getattr(item, "feedback_outcome", None)
    if outcome is None:
        return {}
    normalized = "limited" if outcome == "completed_limited" else outcome
    return {
        "feedback": {
            "outcome": normalized,
            "rpe": getattr(item, "feedback_perceived_exertion", None),
            "reason": getattr(item, "feedback_reason_code", None),
            "savedAt": f"{item.scheduled_date.isoformat()}T12:00:00Z",
        }
    }


def _blocks(item: Any) -> list[dict[str, object]]:
    steps = tuple(getattr(item, "workout_steps", ()) or ())
    if not steps:
        return [
            {
                "id": f"{item.id}-steady",
                "kind": "steady",
                "amount": _scope(item.distance_meters, item.duration_seconds),
                "target": item.target_display or "No separate intensity target",
            }
        ]
    result = []
    for index, step in enumerate(steps):
        kind = "intervals" if step.kind == "interval" else step.kind
        amount = _dose(step.distance_meters, step.duration_seconds)
        if step.repetitions > 1:
            amount = f"{step.repetitions} × {amount}"
        payload: dict[str, object] = {
            "id": f"{item.id}-{index}",
            "kind": kind,
            "amount": amount,
            "target": _target(step.target),
            "note": step.instruction,
        }
        if step.recovery_distance_meters or step.recovery_duration_seconds:
            payload["recovery"] = {
                "amount": _dose(
                    step.recovery_distance_meters, step.recovery_duration_seconds
                ),
                "target": _target(step.recovery_target),
            }
        result.append(payload)
    return result


def _target(target: Any | None) -> str:
    if target is None or target.kind == "none":
        return "No separate intensity target"
    if target.kind == "rpe":
        return f"RPE {target.rpe_min}–{target.rpe_max}"
    if target.kind == "pace" and target.pace_seconds_per_km:
        seconds = target.pace_seconds_per_km
        return f"{seconds // 60}:{seconds % 60:02d}/km"
    if target.kind == "power" and target.power_watts:
        return f"{target.power_watts} W"
    return target.kind


def _dose(distance_meters: float | None, duration_seconds: int | None) -> str:
    if distance_meters is not None:
        return f"{distance_meters / 1_000:g} km"
    if duration_seconds is not None:
        return _duration(duration_seconds)
    return "Unspecified"


def _scope(distance_meters: float | None, duration_seconds: int | None) -> str:
    values = []
    if distance_meters is not None:
        values.append(f"{distance_meters / 1_000:g} km")
    if duration_seconds is not None:
        values.append(_duration(duration_seconds))
    return " · ".join(values) or "Unknown"


def _duration(seconds: int) -> str:
    minutes = round(seconds / 60)
    hours, remainder = divmod(minutes, 60)
    return f"{hours} h {remainder} min" if hours else f"{remainder} min"


def _goal(plan: Any | None, race: Any | None, as_of: date) -> dict[str, object]:
    if plan is None:
        return {
            "label": "No active plan",
            "raceDate": None,
            "daysToRace": None,
            "priority": None,
        }
    if race is None:
        return {
            "label": "General training",
            "raceDate": None,
            "daysToRace": None,
            "priority": None,
        }
    return {
        "label": race.name,
        "raceDate": race.race_date.isoformat(),
        "daysToRace": max((race.race_date - as_of).days, 0),
        "priority": race.priority,
    }


def _plan(
    plan: Any, race: Any | None, checkpoint: Any, as_of: date
) -> dict[str, object]:
    assessment = plan.coach_assessment
    goal = _goal(plan, race, as_of)
    goal.update(
        {
            "sport": "running" if race is None else _sport(race.sport_type),
            "targetTime": _desired_time(race),
            "taperPolicy": "None" if race is None else resolved_taper(race),
        }
    )
    return {
        "planId": str(plan.id),
        "version": int(getattr(plan, "contract_version", 1)),
        "acceptedAt": plan.as_of_date.isoformat(),
        "mode": plan.goal_mode,
        "goal": goal,
        "detailedWindow": {
            "start": plan.detailed_start_date.isoformat(),
            "end": plan.detailed_end_date.isoformat(),
            "generatableFrom": plan.detailed_end_date.isoformat(),
            "sessionCount": len(plan.sessions),
        },
        "revisionDue": getattr(checkpoint, "status", None) == "revision_due",
        "revisionNote": "The active block remains immutable until an explicit revision succeeds.",
        "timeline": _timeline(plan, race, as_of),
        "sessions": [_plan_session(item) for item in plan.sessions],
        "facts": _text_facts("observed", getattr(assessment, "observed_facts", ())),
        "assessment": list(getattr(assessment, "inferences", ()))
        + [assessment.rationale],
        "uncertainty": list(getattr(assessment, "uncertainties", ())),
    }


def _timeline(plan: Any, race: Any | None, as_of: date) -> list[dict[str, object]]:
    result = []
    for index, week in enumerate(plan.block_outline):
        start = date.fromisoformat(str(week["week_start"]))
        end = date.fromisoformat(str(week["week_end"]))
        focus = str(week.get("focus", "Training block"))
        lowered = focus.casefold()
        phase = (
            "taper"
            if "taper" in lowered
            else "specific"
            if plan.goal_mode == "race"
            else "base"
        )
        payload: dict[str, object] = {
            "id": f"week-{index + 1}",
            "label": f"Week {index + 1}",
            "range": f"{start.isoformat()} – {end.isoformat()}",
            "phase": phase,
            "focus": focus,
            "detailed": start <= plan.detailed_end_date
            and end >= plan.detailed_start_date,
            "current": start <= as_of <= end,
        }
        if race is not None and start <= race.race_date <= end:
            payload["phase"] = "race"
            payload["race"] = {
                "label": race.name,
                "date": race.race_date.isoformat(),
                "priority": race.priority,
            }
        result.append(payload)
    return result


def _desired_time(race: Any | None) -> str | None:
    seconds = None if race is None else getattr(race, "desired_time_seconds", None)
    if seconds is None:
        return None
    hours, remainder = divmod(seconds, 3_600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _today_facts(analysis: Any, state: Any) -> list[dict[str, object]]:
    facts = [
        _fact(
            "duration",
            "Training · 28 days",
            f"{analysis.total_duration_hours:.1f}",
            "hours",
        ),
        _fact("active-days", "Active days", str(analysis.total_active_days), "days"),
        _fact(
            "feedback", "Explicit feedback", str(analysis.feedback_records), "records"
        ),
    ]
    for item in state.data_quality.recovery:
        if item.metric == "hrv":
            facts.append(
                _fact(
                    "hrv-coverage",
                    "HRV baseline coverage",
                    str(item.baseline_data_points),
                    "days",
                    coverage=f"{item.baseline_data_points}/{item.expected_baseline_days}",
                )
            )
    return facts


def _fact(
    identifier: str,
    label: str,
    value: str | None,
    unit: str | None = None,
    *,
    detail: str | None = None,
    coverage: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {"id": identifier, "label": label, "value": value}
    if unit is not None:
        payload["unit"] = unit
    if detail is not None:
        payload["detail"] = detail
    if coverage is not None:
        payload["coverage"] = coverage
    return payload


def _text_facts(prefix: str, values: Any) -> list[dict[str, object]]:
    return [
        _fact(f"{prefix}-{index}", "Observation", str(value))
        for index, value in enumerate(values, 1)
    ]


def _freshness(state: Any, as_of: date) -> str:
    sync = state.data_quality.latest_completed_sync
    if sync is None or sync.requested_end_date is None:
        return "unknown"
    if sync.status == "partial":
        return "partial"
    return "current" if (as_of - sync.requested_end_date).days <= 1 else "stale"


def _data_quality(state: Any, as_of: date) -> dict[str, object]:
    sync = state.data_quality.latest_completed_sync
    recovery = state.data_quality.recovery
    warnings = []
    for item in recovery:
        if item.baseline_data_points < item.expected_baseline_days:
            warnings.append(
                f"{item.metric.replace('_', ' ')} has {item.baseline_data_points} of "
                f"{item.expected_baseline_days} expected baseline days."
            )
    if sync is None:
        warnings.append("No completed Garmin sync is available.")
    return {
        "freshness": _freshness(state, as_of),
        "lastSyncAt": None if sync is None else sync.completed_at.isoformat(),
        "coverageNote": " · ".join(
            f"{item.metric}: {item.baseline_data_points}/{item.expected_baseline_days}"
            for item in recovery
        )
        or "Recovery coverage is unknown.",
        "warnings": warnings,
    }


def _today_rationale(plan: Any | None, session: Any | None) -> str:
    if plan is None:
        return "No active plan is available. Create one explicitly from Coach."
    if session is None:
        return "No detailed session remains in the active plan window."
    rationale = getattr(plan.coach_assessment, "rationale", "")
    return rationale or session.purpose


def _action_needed(freshness: str, plan: Any | None, session: Any | None) -> list[str]:
    actions = []
    if freshness in {"stale", "unknown"}:
        actions.append(
            "Garmin data is not current. Start an explicit sync before making a new training decision."
        )
    if plan is None:
        actions.append("No active plan exists.")
    elif session is None:
        actions.append("The active plan has no remaining detailed session.")
    return actions


def _dashboard(data: Any, days: int, as_of: date) -> dict[str, object]:
    dates = tuple(as_of - timedelta(days=offset) for offset in range(days - 1, -1, -1))
    seconds = defaultdict(int)
    distance = defaultdict(float)
    count = defaultdict(int)
    for activity in data.activities:
        if activity.sport_type not in {"run", "ride"}:
            continue
        day = athlete_local_date(activity.start_time)
        seconds[day, activity.sport_type] += activity.duration_seconds or 0
        if activity.distance_meters is not None:
            distance[activity.sport_type] += activity.distance_meters
        count[activity.sport_type] += 1
    recovery = {item.date: item for item in data.recovery_observations}
    charts = [
        _chart(
            "training",
            f"Training · {days} days",
            "bar",
            "hours",
            dates,
            (
                (
                    "run",
                    "Running",
                    "run",
                    [seconds[day, "run"] / 3_600 for day in dates],
                ),
                (
                    "ride",
                    "Cycling",
                    "ride",
                    [seconds[day, "ride"] / 3_600 for day in dates],
                ),
            ),
        ),
        _chart(
            "hrv",
            "HRV",
            "line",
            "ms",
            dates,
            (
                (
                    "hrv",
                    "HRV",
                    "forest",
                    [
                        recovery.get(day).hrv_value if day in recovery else None
                        for day in dates
                    ],
                ),
            ),
        ),
        _chart(
            "rhr",
            "Resting heart rate",
            "line",
            "bpm",
            dates,
            (
                (
                    "rhr",
                    "Resting heart rate",
                    "warning",
                    [
                        recovery.get(day).resting_heart_rate
                        if day in recovery
                        else None
                        for day in dates
                    ],
                ),
            ),
        ),
        _chart(
            "sleep",
            "Sleep duration",
            "line",
            "hours",
            dates,
            (
                (
                    "sleep",
                    "Sleep",
                    "accent",
                    [
                        recovery.get(day).sleep_duration_hours
                        if day in recovery
                        else None
                        for day in dates
                    ],
                ),
            ),
        ),
    ]
    state = data.state
    return {
        "window": days,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "runTiles": [
            _fact("run-count", "Running sessions", str(count["run"])),
            _fact(
                "run-hours",
                "Running time",
                f"{sum(seconds[day, 'run'] for day in dates) / 3_600:.1f}",
                "hours",
            ),
            _fact(
                "run-distance",
                "Known running distance",
                f"{distance['run'] / 1_000:.1f}",
                "km",
            ),
        ],
        "rideTiles": [
            _fact("ride-count", "Cycling sessions", str(count["ride"])),
            _fact(
                "ride-hours",
                "Cycling time",
                f"{sum(seconds[day, 'ride'] for day in dates) / 3_600:.1f}",
                "hours",
            ),
            _fact(
                "ride-distance",
                "Known cycling distance",
                f"{distance['ride'] / 1_000:.1f}",
                "km",
            ),
        ],
        "recoveryTiles": [
            _fact(
                item.metric,
                item.metric.replace("_", " ").title(),
                str(item.baseline_data_points),
                "days",
                coverage=f"{item.baseline_data_points}/{item.expected_baseline_days}",
            )
            for item in state.data_quality.recovery
        ],
        "charts": charts,
        "coverage": [
            _fact(
                item.metric,
                item.metric.replace("_", " ").title(),
                str(item.baseline_data_points),
                "days",
                coverage=f"{item.baseline_data_points}/{item.expected_baseline_days}",
            )
            for item in state.data_quality.recovery
        ],
        "dataQuality": _data_quality(state, as_of),
        "assessment": [],
        "uncertainty": list(getattr(data.trends, "limitations", ())),
    }


def _chart(
    identifier: str, title: str, kind: str, unit: str, dates: Any, series: Any
) -> dict[str, object]:
    return {
        "id": identifier,
        "title": title,
        "note": "Locally stored normalized Pace facts. Missing observations remain gaps.",
        "kind": kind,
        "unit": unit,
        "xLabel": "Stockholm date",
        "yLabel": unit,
        "series": [
            {
                "id": series_id,
                "label": label,
                "unit": unit,
                "color": color,
                "points": [
                    {
                        "x": day.isoformat(),
                        "label": day.strftime("%d %b"),
                        "value": value,
                    }
                    for day, value in zip(dates, values, strict=True)
                ],
            }
            for series_id, label, color, values in series
        ],
        "coverage": f"{len(dates)} calendar days",
    }


def _race(item: Any, active_race_id: int | None) -> dict[str, object]:
    return {
        "id": str(item.id),
        "name": item.name,
        "sport": _sport(item.sport_type),
        "date": item.race_date.isoformat(),
        "distance": f"{item.distance_meters / 1_000:g} km",
        "priority": item.priority,
        "desiredTime": _desired_time(item),
        "taperPolicy": resolved_taper(item),
        "status": "cancelled" if item.status == "cancelled" else "planned",
        "isPlanTarget": item.id == active_race_id,
    }


def _availability(preference: Any | None) -> list[dict[str, object]]:
    selected = (
        {}
        if preference is None
        else {item["day"]: item.get("minutes") for item in preference.available_days}
    )
    labels = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    return [
        {"day": day, "available": day in selected, "capMinutes": selected.get(day)}
        for day in labels
    ]


def _zones(profile: Any | None) -> list[dict[str, object]]:
    if profile is None:
        return [
            {"id": str(zone), "label": f"Zone {zone}", "from": None, "to": None}
            for zone in range(1, 6)
        ]
    return [
        {
            "id": str(item["zone"]),
            "label": f"Zone {item['zone']}",
            "from": item["lower_bpm"],
            "to": item["upper_bpm"],
        }
        for item in profile.zones
    ]
