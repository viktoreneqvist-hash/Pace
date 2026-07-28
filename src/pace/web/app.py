"""Loopback-only web application that reuses Pace's existing service boundaries."""

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
import secrets
from pathlib import Path
import re
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import AliasChoices, BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from pace.ai.client import PaceAIError
from pace.coach.client import OpenAICoachDialogueClient
from pace.config.settings import PROJECT_ROOT, resolve_openai_api_key, settings
from pace.integrations.garmin.client import (
    GarminAuthenticationRequiredError,
    GarminConnectClient,
    GarminIntegrationError,
    GarminRateLimitError,
)
from pace.presentation.dashboard import render_dashboard_fragment
from pace.presentation.plan_views import render_plan_fragment
from pace.presentation.weekly_review import (
    load_weekly_review_snapshot,
    render_weekly_review_fragment,
)
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
from pace.services.dashboard_service import DashboardService
from pace.services.garmin_sync_service import GarminSyncService
from pace.services.weekly_review_service import WeeklyReviewService
from pace.web.presentation import render_web_home, render_web_report_page
from pace.weekly_review.client import WeeklyReviewClient


STATIC_DIR = Path(__file__).with_name("static")
REPORTS_DIRECTORY = PROJECT_ROOT / "reports"
MAX_CONVERSATION_MESSAGES = 8
SAFE_REPORT_NAME = re.compile(r"(?:dashboard|home|weekly-review|plan-[1-9][0-9]*)\.html")


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)


class CommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=100)


class CommandConfirmation(BaseModel):
    action: str = Field(min_length=1, max_length=30)


class ContextConfirmation(BaseModel):
    event_type: str
    start_date: date
    end_date: date | None = None
    ongoing: bool = False
    note: str = Field(min_length=1, max_length=2_000)


class FeedbackConfirmation(BaseModel):
    session_id: int = Field(
        validation_alias=AliasChoices("session_id", "planned_session_id")
    )
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
    dashboard_service: Any = field(default_factory=DashboardService)
    context_service: Any = field(default_factory=ContextService)
    reports_directory: Path = REPORTS_DIRECTORY
    coach_service_factory: Callable[[], CoachDialogueService] | None = None
    sync_service_factory: Callable[[], GarminSyncService] | None = None
    weekly_review_service_factory: Callable[[], WeeklyReviewService] | None = None
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

    def sync_service(self) -> GarminSyncService:
        if self.sync_service_factory is not None:
            return self.sync_service_factory()
        client = GarminConnectClient.from_saved_tokens(settings.garmin_token_dir)
        return GarminSyncService(client)

    def weekly_review_service(self) -> WeeklyReviewService:
        if self.weekly_review_service_factory is not None:
            return self.weekly_review_service_factory()
        api_key = resolve_openai_api_key(settings)
        if not api_key:
            raise ValueError("OPENAI_API_KEY saknas; veckoreview kan inte startas.")
        return WeeklyReviewService(
            client=WeeklyReviewClient(api_key=api_key, model=settings.openai_model)
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

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        _session_value(request, "csrf_token")
        state = _home_state(dependencies)
        data = dependencies.dashboard_service.get_dashboard_data(
            end_date=dependencies.today()
        )
        return _html_response(
            render_web_report_page(
                state=state,
                active_page="dashboard",
                kicker="AKTUELL FAKTAVY",
                title="Dashboard",
                subtitle="Aktuella lokala tränings- och återhämtningsfakta. Ingen AI körs här.",
                body_html=render_dashboard_fragment(
                    state=data.state,
                    trends=data.trends,
                    plan=data.plan,
                    activities=data.activities,
                    recovery_observations=data.recovery_observations,
                ),
            )
        )

    @app.get("/plan", response_class=HTMLResponse)
    def plan(request: Request) -> HTMLResponse:
        _session_value(request, "csrf_token")
        state = _home_state(dependencies)
        active_plan = _active_plan(
            dependencies.plan_service.list_plans(), dependencies.today()
        )
        if active_plan is None:
            body_html = (
                '<section class="report-section"><h2>Ingen aktiv plan</h2>'
                '<p>Det finns ingen accepterad plan för dagens datum. Skapa och acceptera '
                'ett nytt utkast i Pace när planeringsunderlaget är klart.</p></section>'
            )
            subtitle = "Den här vyn visar alltid den accepterade planen som gäller i dag."
        else:
            body_html = render_plan_fragment(active_plan)
            subtitle = "Accepterad plan som gäller i dag. Feedback syns här efter att den har sparats."
        return _html_response(
            render_web_report_page(
                state=state,
                active_page="plan",
                kicker="ACCEPTERAD PLAN",
                title="Plan",
                subtitle=subtitle,
                body_html=body_html,
            )
        )

    @app.get("/weekly-review", response_class=HTMLResponse)
    def weekly_review(request: Request) -> HTMLResponse:
        _session_value(request, "csrf_token")
        state = _home_state(dependencies)
        snapshot = load_weekly_review_snapshot(
            reports_directory=dependencies.reports_directory
        )
        if snapshot is None:
            body_html = (
                '<section class="report-section"><h2>Ingen kompatibel veckoreview ännu</h2>'
                '<p>Skapa en ny explicit review i terminalen för att visa den här. '
                'Pace gör inte ett AI-anrop automatiskt när du öppnar sidan.</p>'
                '<p class="notice">Kör: uv run pace review weekly</p></section>'
            )
            subtitle = "Veckoreview sparas som en uttrycklig AI-snapshot."
        else:
            body_html = render_weekly_review_fragment(snapshot)
            subtitle = (
                "Senaste uttryckliga AI-snapshoten för veckan som slutar "
                f"{snapshot.end_date.isoformat()}."
            )
        return _html_response(
            render_web_report_page(
                state=state,
                active_page="weekly_review",
                kicker="EXPLICIT AI-REVIEW",
                title="Veckoreview",
                subtitle=subtitle,
                body_html=body_html,
            )
        )

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

    @app.post("/api/command")
    def command(request: Request, payload: CommandRequest) -> dict[str, object]:
        """Handle the small, explicit web command palette without an AI call."""

        _require_csrf(request)
        state = _home_state(dependencies)
        normalized = " ".join(payload.command.casefold().split())
        if normalized == "/help":
            return {
                "answer": (
                    "Kommandon: /today visar nästa planerade pass, /state visar "
                    "aktuell Pace-status, /analysis visar 28-dagarsfakta, /sync "
                    "förbereder Garmin-synk och /review weekly förbereder en AI-review."
                )
            }
        if normalized == "/today":
            return {"answer": _today_command_answer(state)}
        if normalized == "/state":
            return {"answer": _state_command_answer(state)}
        if normalized == "/analysis":
            return {"answer": _analysis_command_answer(state)}
        if normalized == "/sync":
            return {
                "answer": "Garmin-synk är förberedd men har inte startat.",
                "confirmation": {
                    "action": "sync",
                    "title": "Synka Garmin",
                    "body": "Hämtar de senaste sju kalenderdagarna till din lokala Pace-databas.",
                    "label": "Starta synk",
                    "values": [["Period", _sync_window_label(dependencies.today())]],
                },
            }
        if normalized == "/review weekly":
            return {
                "answer": "Veckoreview är förberedd men AI-anropet har inte startat.",
                "confirmation": {
                    "action": "weekly_review",
                    "title": "Skapa veckoreview",
                    "body": "Skapar en ny daterad AI-review av lokala Pace-fakta. Det använder din OpenAI-nyckel och kan kosta pengar.",
                    "label": "Skapa veckoreview",
                    "values": [["Vecka slutar", dependencies.today().isoformat()]],
                },
            }
        raise HTTPException(
            status_code=422,
            detail="Okänt kommando. Skriv /help för tillgängliga kommandon.",
        )

    @app.post("/api/command/confirm")
    def confirm_command(
        request: Request, payload: CommandConfirmation
    ) -> dict[str, object]:
        """Run only a reviewed, user-confirmed command; never a shell command."""

        _require_csrf(request)
        if payload.action == "sync":
            end_date = dependencies.today()
            try:
                result = dependencies.sync_service().sync(
                    start_date=end_date - timedelta(days=6), end_date=end_date
                )
            except GarminAuthenticationRequiredError as error:
                raise HTTPException(
                    status_code=422, detail=f"Synken kan inte starta: {error}"
                ) from error
            except GarminRateLimitError as error:
                raise HTTPException(
                    status_code=429, detail=f"Garmin begränsade synken: {error}"
                ) from error
            except (GarminIntegrationError, ValueError) as error:
                raise HTTPException(
                    status_code=422, detail=f"Synken misslyckades: {error}"
                ) from error
            return {
                "status": "completed",
                "action": "sync",
                "message": _sync_command_result(result),
            }
        if payload.action == "weekly_review":
            try:
                path = dependencies.weekly_review_service().create(
                    end_date=dependencies.today()
                )
            except (PaceAIError, ValueError) as error:
                raise HTTPException(
                    status_code=422, detail=str(error)
                ) from error
            return {
                "status": "completed",
                "action": "weekly_review",
                "message": "Veckoreview skapad. Öppna fliken Veckoreview för att läsa den.",
                "path": str(path.name),
            }
        raise HTTPException(status_code=422, detail="Otillåtet Pace-kommando.")

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


def _html_response(content: str) -> HTMLResponse:
    return HTMLResponse(content, headers={"Cache-Control": "no-store"})


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
        "dashboard": ("/dashboard", True, ""),
        "weekly_review": (
            "/weekly-review",
            load_weekly_review_snapshot(reports_directory=reports_directory) is not None,
            "Kör: uv run pace review weekly",
        ),
        "plan": (
            "/plan",
            active_plan is not None,
            "Skapa eller öppna en accepterad plan först.",
        ),
    }
    result: dict[str, dict[str, object]] = {}
    for key, (path, available, unavailable_message) in candidates.items():
        result[key] = {
            "path": path,
            "available": available,
            "unavailable_message": unavailable_message,
        }
    return result


def _today_command_answer(state: dict[str, object]) -> str:
    plan = state["active_plan"]
    if not isinstance(plan, dict):
        return "Ingen accepterad aktiv plan finns för i dag."
    as_of_date = str(state["as_of_date"])
    sessions = plan["sessions"]
    upcoming = [item for item in sessions if item["scheduled_date"] >= as_of_date]
    if not upcoming:
        return "Inga detaljerade pass återstår i den accepterade planen."
    session = upcoming[0]
    when = "I dag" if session["scheduled_date"] == as_of_date else session["scheduled_date"]
    return (
        f"{when}: {session['sport_type']} · {session['purpose']} · "
        f"{session['target_display']}."
    )


def _state_command_answer(state: dict[str, object]) -> str:
    checkpoint = state["checkpoint"]
    plan = state["active_plan"]
    plan_label = "ingen accepterad aktiv plan" if plan is None else f"plan {plan['id']}"
    return (
        f"Pace-status {state['as_of_date']}: {plan_label}; "
        f"planstatus {checkpoint['status']}; "
        f"{checkpoint['detailed_days_remaining']} dagar kvar i detaljfönstret."
    )


def _analysis_command_answer(state: dict[str, object]) -> str:
    analysis = state["analysis"]
    sports = {item["sport_type"]: item for item in analysis["sports"]}
    run = sports.get("run", {})
    ride = sports.get("ride", {})
    return (
        f"Senaste 28 dagarna: {analysis['total_duration_hours']:.1f} h totalt · "
        f"löpning {run.get('activity_count', 0)} pass / "
        f"{run.get('duration_hours', 0):.1f} h · cykel "
        f"{ride.get('activity_count', 0)} pass / "
        f"{ride.get('duration_hours', 0):.1f} h."
    )


def _sync_window_label(end_date: date) -> str:
    return f"{end_date - timedelta(days=6)} till {end_date}"


def _sync_command_result(result) -> str:
    return (
        f"Garmin-synk klar ({result.start_date} till {result.end_date}): "
        f"{result.activities_fetched} hämtade, {result.activities_inserted} nya och "
        f"{result.activities_updated} uppdaterade aktiviteter; "
        f"{result.daily_metrics_fetched} recovery-dagar."
    )


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
