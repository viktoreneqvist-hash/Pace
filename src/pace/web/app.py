"""Loopback-only web application that reuses Pace's existing service boundaries."""

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date
import secrets
from pathlib import Path
import re
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from pace.ai.client import PaceAIError
from pace.coach.client import OpenAICoachDialogueClient
from pace.config.settings import PROJECT_ROOT, resolve_openai_api_key, settings
from pace.services.context_service import ContextEventInput, ContextService
from pace.services.heart_rate_zone_service import HeartRateZoneService
from pace.services.personalization_evidence_service import PersonalizationEvidenceService
from pace.services.plan_checkpoint_service import PlanCheckpointService
from pace.services.race_service import RaceService, resolved_taper
from pace.services.training_plan_service import TrainingPlanService
from pace.services.training_preference_service import TrainingPreferenceService
from pace.services.transparent_training_analysis_service import (
    TransparentTrainingAnalysisService,
)
from pace.services.coach_dialogue_service import CoachDialogueService
from pace.web.presentation import render_web_home


STATIC_DIR = Path(__file__).with_name("static")
REPORTS_DIRECTORY = PROJECT_ROOT / "reports"
MAX_CONVERSATION_MESSAGES = 8
SAFE_REPORT_NAME = re.compile(r"(?:dashboard|home|weekly-review|plan-[1-9][0-9]*)\.html")


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)


class ContextConfirmation(BaseModel):
    event_type: str
    start_date: date
    end_date: date | None = None
    ongoing: bool = False
    note: str = Field(min_length=1, max_length=2_000)


class FeedbackConfirmation(BaseModel):
    session_id: int
    outcome: str
    perceived_exertion: int | None = Field(default=None, ge=1, le=10)
    reason_code: str | None = None
    note: str | None = Field(default=None, max_length=2_000)
    share_note_with_ai: bool = False


@dataclass(slots=True)
class WebServices:
    """Dependency bundle that keeps HTTP thin and makes synthetic tests simple."""

    plan_service: Any = field(default_factory=TrainingPlanService)
    checkpoint_service: Any = field(default_factory=PlanCheckpointService)
    preference_service: Any = field(default_factory=TrainingPreferenceService)
    zone_service: Any = field(default_factory=HeartRateZoneService)
    personalization_service: Any = field(default_factory=PersonalizationEvidenceService)
    race_service: Any = field(default_factory=RaceService)
    analysis_service: Any = field(default_factory=TransparentTrainingAnalysisService)
    context_service: Any = field(default_factory=ContextService)
    reports_directory: Path = REPORTS_DIRECTORY
    coach_service_factory: Callable[[], CoachDialogueService] | None = None
    today: Callable[[], date] = date.today

    def coach_service(self) -> CoachDialogueService:
        if self.coach_service_factory is not None:
            return self.coach_service_factory()
        api_key = resolve_openai_api_key(settings)
        if not api_key:
            raise ValueError("OPENAI_API_KEY saknas; coachchatten kan inte startas.")
        return CoachDialogueService(
            client=OpenAICoachDialogueClient(
                api_key=api_key,
                model=settings.openai_model,
            )
        )


def create_app(*, services: WebServices | None = None) -> FastAPI:
    """Create a same-origin UI, bound by the CLI command to loopback only."""

    dependencies = services or WebServices()
    conversations: dict[str, list[dict[str, str]]] = {}
    app = FastAPI(title="Pace Local Coach", docs_url=None, redoc_url=None)
    app.add_middleware(
        SessionMiddleware,
        secret_key=secrets.token_urlsafe(32),
        same_site="lax",
        https_only=False,
    )
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        csrf_token = _session_value(request, "csrf_token")
        state = _home_state(dependencies)
        return HTMLResponse(render_web_home(state=state, csrf_token=csrf_token))

    @app.get("/api/home")
    def api_home(request: Request) -> dict[str, object]:
        _session_value(request, "csrf_token")
        return _home_state(dependencies)

    @app.get("/reports/{report_name}")
    def report(report_name: str) -> FileResponse:
        report_path = _safe_report_path(dependencies.reports_directory, report_name)
        if report_path is None or not report_path.is_file():
            raise HTTPException(
                status_code=404,
                detail="Rapporten finns inte ännu. Skapa den från Pace-terminalen först.",
            )
        return FileResponse(
            report_path,
            media_type="text/html",
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/api/chat")
    def chat(request: Request, payload: ChatRequest) -> dict[str, object]:
        _require_csrf(request)
        as_of_date = dependencies.today()
        plan = _active_plan(dependencies.plan_service.list_plans(), as_of_date)
        if plan is None:
            raise HTTPException(
                status_code=409,
                detail="Coachchatten kräver en accepterad aktiv plan.",
            )
        session_id = _session_value(request, "conversation_id")
        conversation = tuple(conversations.get(session_id, ()))
        try:
            answer = dependencies.coach_service().ask(
                question=payload.question,
                plan=plan,
                end_date=as_of_date,
                conversation=conversation,
            )
        except (ValueError, PaceAIError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        conversations[session_id] = [
            *conversation,
            {"role": "athlete", "text": payload.question.strip()},
            {"role": "coach", "text": answer.answer},
        ][-MAX_CONVERSATION_MESSAGES:]
        return _coach_answer_payload(answer)

    @app.post("/api/context/confirm")
    def confirm_context(request: Request, payload: ContextConfirmation) -> dict[str, object]:
        _require_csrf(request)
        try:
            event = dependencies.context_service.add_event(
                ContextEventInput(
                    event_type=payload.event_type,
                    start_date=payload.start_date,
                    end_date=payload.end_date,
                    ongoing=payload.ongoing,
                    note=payload.note,
                )
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"status": "saved", "event_id": event.id}

    @app.post("/api/feedback/confirm")
    def confirm_feedback(request: Request, payload: FeedbackConfirmation) -> dict[str, object]:
        _require_csrf(request)
        try:
            dependencies.plan_service.add_feedback(
                session_id=payload.session_id,
                outcome=payload.outcome,
                perceived_exertion=payload.perceived_exertion,
                reason_code=payload.reason_code,
                note=payload.note,
                share_note_with_ai=payload.share_note_with_ai,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"status": "saved", "session_id": payload.session_id}

    return app


def _session_value(request: Request, key: str) -> str:
    value = request.session.get(key)
    if isinstance(value, str) and value:
        return value
    value = secrets.token_urlsafe(24)
    request.session[key] = value
    return value


def _require_csrf(request: Request) -> None:
    expected = _session_value(request, "csrf_token")
    supplied = request.headers.get("X-Pace-CSRF")
    if not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=403, detail="Ogiltig lokal bekräftelse.")


def _home_state(services: WebServices) -> dict[str, object]:
    as_of_date = services.today()
    plans = services.plan_service.list_plans()
    active_plan = _active_plan(plans, as_of_date)
    checkpoint = services.checkpoint_service.get_checkpoint(as_of_date=as_of_date)
    preference = services.preference_service.get_preference()
    zones = services.zone_service.get_profile(sport_type="ride")
    personalization = services.personalization_service.get_evidence(end_date=as_of_date)
    analysis = services.analysis_service.get_analysis(end_date=as_of_date)
    races = services.race_service.list_upcoming_races(as_of_date=as_of_date)
    return {
        "as_of_date": as_of_date.isoformat(),
        "checkpoint": _jsonable(checkpoint),
        "active_plan": _plan_payload(active_plan),
        "reports": _reports_payload(services.reports_directory, active_plan),
        "preference": _preference_payload(preference),
        "ride_zones": None if zones is None else _jsonable(zones.zones),
        "personalization": _jsonable(personalization),
        "analysis": _jsonable(analysis),
        "races": [_race_payload(race) for race in races],
    }


def _active_plan(plans, as_of_date: date):
    return next(
        (
            plan
            for plan in plans
            if plan.status == "accepted"
            and plan.block_start_date <= as_of_date <= plan.block_end_date
        ),
        None,
    )


def _plan_payload(plan) -> dict[str, object] | None:
    if plan is None:
        return None
    return {
        "id": plan.id,
        "status": plan.status,
        "goal_mode": plan.goal_mode,
        "block_start_date": plan.block_start_date.isoformat(),
        "block_end_date": plan.block_end_date.isoformat(),
        "detailed_end_date": plan.detailed_end_date.isoformat(),
        "sessions": [
            {
                "id": session.id,
                "scheduled_date": session.scheduled_date.isoformat(),
                "sport_type": session.sport_type,
                "purpose": session.purpose,
                "distance_meters": session.distance_meters,
                "duration_seconds": session.duration_seconds,
                "target_display": session.target_display,
                "feedback_outcome": session.feedback_outcome,
            }
            for session in plan.sessions
        ],
    }


def _preference_payload(preference) -> dict[str, object] | None:
    if preference is None:
        return None
    return {
        "sport_role": preference.sport_role,
        "coaching_ambition": preference.coaching_ambition,
        "available_days": preference.available_days,
    }


def _race_payload(race) -> dict[str, object]:
    return {
        "id": race.id,
        "name": race.name,
        "race_date": race.race_date.isoformat(),
        "sport_type": race.sport_type,
        "priority": race.priority,
        "taper": resolved_taper(race),
    }


def _safe_report_path(reports_directory: Path, report_name: str) -> Path | None:
    """Allow only Pace's generated local HTML reports, never arbitrary files."""

    if not SAFE_REPORT_NAME.fullmatch(report_name):
        return None
    directory = reports_directory.resolve()
    candidate = (directory / report_name).resolve()
    return candidate if candidate.parent == directory else None


def _reports_payload(reports_directory: Path, active_plan) -> dict[str, dict[str, object]]:
    candidates = {
        "dashboard": ("dashboard.html", "Kör: uv run pace dashboard"),
        "weekly_review": ("weekly-review.html", "Kör: uv run pace review weekly"),
        "plan": (
            None if active_plan is None else f"plan-{active_plan.id}.html",
            "Skapa eller öppna en accepterad plan först.",
        ),
    }
    result: dict[str, dict[str, object]] = {}
    for key, (name, unavailable_message) in candidates.items():
        path = None if name is None else _safe_report_path(reports_directory, name)
        result[key] = {
            "path": None if path is None else f"/reports/{path.name}",
            "available": path is not None and path.is_file(),
            "unavailable_message": unavailable_message,
        }
    return result


def _coach_answer_payload(answer) -> dict[str, object]:
    return {
        "answer": answer.answer,
        "observations": list(answer.observations),
        "uncertainties": list(answer.uncertainties),
        "knowledge_references": list(answer.knowledge_references),
        "adjustment_draft": _jsonable(answer.adjustment_draft),
        "context_event_draft": _jsonable(answer.context_event_draft),
        "feedback_draft": _jsonable(answer.feedback_draft),
    }


def _jsonable(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    try:
        return _jsonable(asdict(value))
    except TypeError:
        return str(value)
