"""Command-line entry point for the Pace application."""

from argparse import ArgumentParser, ArgumentTypeError, Namespace
from dataclasses import asdict
from datetime import date, timedelta
from getpass import getpass
import json
import shlex
from threading import Timer
import webbrowser

from sqlalchemy.exc import OperationalError

from pace.config.settings import resolve_openai_api_key, settings
from pace.database.initialization import initialize_database
from pace.integrations.garmin import (
    GarminAuthenticationRequiredError,
    GarminConnectClient,
    GarminIntegrationError,
    GarminRateLimitError,
)
from pace.services.garmin_sync_service import MAX_SYNC_DAYS, GarminSyncService
from pace.services.context_service import (
    SUPPORTED_CONTEXT_EVENT_TYPES,
    ContextEventInput,
    ContextService,
)
from pace.services.metric_service import MetricService
from pace.services.rule_service import RuleService
from pace.services.athlete_state_service import AthleteStateService
from pace.services.explanation_service import ExplanationService
from pace.explanations.hrv import render_explanation_summary
from pace.ai.client import OpenAIResponsesClient, PaceAIError
from pace.ai.models import ContextEventDraft, PaceAIAnswer
from pace.coach.client import OpenAICoachDialogueClient
from pace.coach.models import CoachDialogueAnswer
from pace.knowledge.library import (
    KnowledgeLibraryError,
    brief_by_id,
    load_knowledge_library,
    source_by_id,
)
from pace.services.ai_ask_service import PaceAskService
from pace.services.coach_dialogue_service import CoachDialogueService
from pace.services.plan_readiness_service import PlanReadinessService
from pace.services.race_service import (
    SUPPORTED_RACE_PRIORITIES,
    SUPPORTED_RACE_SPORT_TYPES,
    SUPPORTED_TAPER_CHOICES,
    RaceInput,
    RaceService,
    resolved_taper,
)
from pace.services.capacity_service import CapacityService
from pace.services.performance_history_service import PerformanceHistoryService
from pace.performance.protocols import SUPPORTED_BENCHMARK_PROTOCOLS
from pace.ai.plan_client import OpenAIPlanClient
from pace.services.training_plan_service import (
    SUPPORTED_FEEDBACK_REASON_CODES,
    SUPPORTED_FEEDBACK_OUTCOMES,
    TrainingPlanService,
)
from pace.services.training_response_trend_service import TrainingResponseTrendService
from pace.services.dashboard_service import DashboardService
from pace.services.coaching_principle_service import CoachingPrincipleService
from pace.services.weekly_review_service import WeeklyReviewService
from pace.services.workout_evaluation_service import WorkoutEvaluationService
from pace.services.plan_checkpoint_service import PlanCheckpointService
from pace.services.home_service import HomeService
from pace.services.coach_evaluation_service import CoachEvaluationService
from pace.services.transparent_training_analysis_service import (
    TransparentTrainingAnalysisService,
)
from pace.coach_evaluation.scenarios import load_scenarios
from pace.weekly_review.client import WeeklyReviewClient
from pace.services.training_preference_service import (
    SUPPORTED_COACHING_AMBITIONS,
    SUPPORTED_SPORT_ROLES,
    TrainingPreferenceInput,
    TrainingPreferenceService,
)
from pace.services.heart_rate_zone_service import HeartRateZoneInput, HeartRateZoneService
from pace.presentation.plan_views import (
    render_plan_review,
    render_plan_today,
    select_plan_for_today,
    write_plan_html_report,
)


def positive_days(value: str) -> int:
    """Parse a bounded synchronization window length."""

    try:
        days = int(value)
    except ValueError as error:
        raise ArgumentTypeError("--days måste vara ett heltal.") from error

    if days < 1:
        raise ArgumentTypeError("--days måste vara minst 1.")
    if days > MAX_SYNC_DAYS:
        raise ArgumentTypeError(
            f"--days får vara högst {MAX_SYNC_DAYS}. "
            "Använd --end-date för äldre sjudagarsbatcher."
        )

    return days


def plan_days(value: str) -> int:
    try:
        days = int(value)
    except ValueError as error:
        raise ArgumentTypeError("--days måste vara 7 eller 14.") from error
    if days not in {7, 14}:
        raise ArgumentTypeError("--days måste vara 7 eller 14.")
    return days


def feedback_rpe(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ArgumentTypeError("--rpe måste vara ett heltal från 1 till 10.") from error
    if not 1 <= parsed <= 10:
        raise ArgumentTypeError("--rpe måste vara mellan 1 och 10.")
    return parsed


def local_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise ArgumentTypeError("--port måste vara ett heltal mellan 1024 och 65535.") from error
    if not 1024 <= port <= 65_535:
        raise ArgumentTypeError("--port måste vara mellan 1024 och 65535.")
    return port


def iso_date(value: str) -> date:
    """Parse an ISO calendar date supplied to the CLI."""

    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ArgumentTypeError("Datum måste ha formatet YYYY-MM-DD.") from error


def positive_distance_km(value: str) -> float:
    """Parse a positive race distance in the athlete-facing unit."""

    try:
        distance_km = float(value)
    except ValueError as error:
        raise ArgumentTypeError("Distans måste vara ett tal i kilometer.") from error
    if distance_km <= 0:
        raise ArgumentTypeError("Distans måste vara större än noll.")
    return distance_km


def duration_seconds(value: str) -> int:
    """Parse an optional race goal time in H:MM:SS format."""

    parts = value.split(":")
    if len(parts) != 3:
        raise ArgumentTypeError("Önskad tid måste ha formatet H:MM:SS.")
    try:
        hours, minutes, seconds = (int(part) for part in parts)
    except ValueError as error:
        raise ArgumentTypeError("Önskad tid måste ha formatet H:MM:SS.") from error
    if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
        raise ArgumentTypeError("Önskad tid måste ha formatet H:MM:SS.")
    total_seconds = hours * 3600 + minutes * 60 + seconds
    if total_seconds <= 0:
        raise ArgumentTypeError("Önskad tid måste vara större än noll.")
    return total_seconds


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        prog="pace",
        description="A private, local-first endurance coaching system.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="pace 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command")

    db_parser = subparsers.add_parser(
        "db",
        help="initiera och uppgradera den lokala databasen",
    )
    db_subparsers = db_parser.add_subparsers(dest="db_command")
    db_init_parser = db_subparsers.add_parser(
        "init",
        help="applicera Pace-databasens Alembic-migreringar",
    )
    db_init_parser.set_defaults(handler=run_db_init)

    garmin_parser = subparsers.add_parser(
        "garmin",
        help="hantera Garmin-inloggning",
    )
    garmin_subparsers = garmin_parser.add_subparsers(dest="garmin_command")
    login_parser = garmin_subparsers.add_parser(
        "login",
        help="logga in och spara en lokal Garmin-session",
    )
    login_parser.add_argument(
        "--email",
        help="Garmin-e-post. Utelämna för att skriva den i en privat prompt.",
    )
    login_parser.set_defaults(handler=run_garmin_login)

    sync_parser = subparsers.add_parser(
        "sync",
        help="hämta Garmin-aktiviteter och recovery till den lokala databasen",
    )
    sync_parser.add_argument(
        "--days",
        type=positive_days,
        default=7,
        help="antal kalenderdagar inklusive batchens slutdatum (standard: 7)",
    )
    sync_parser.add_argument(
        "--end-date",
        type=iso_date,
        help=(
            "sista datum i batchen, YYYY-MM-DD "
            "(standard: idag; använd för äldre historik)"
        ),
    )
    sync_parser.set_defaults(handler=run_sync)

    note_parser = subparsers.add_parser(
        "note",
        help="spara och visa lokal atletkontext",
    )
    note_subparsers = note_parser.add_subparsers(dest="note_command")
    note_add_parser = note_subparsers.add_parser(
        "add",
        help="spara en strukturerad context-not",
    )
    note_add_parser.add_argument(
        "--type",
        dest="event_type",
        choices=sorted(SUPPORTED_CONTEXT_EVENT_TYPES),
        required=True,
        help="typ av kontext som Garmin inte kan observera",
    )
    note_add_parser.add_argument(
        "--date",
        dest="start_date",
        type=iso_date,
        required=True,
        help="första datumet för händelsen, YYYY-MM-DD",
    )
    note_add_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="sista datumet för en tidsbegränsad händelse, YYYY-MM-DD",
    )
    note_add_parser.add_argument(
        "--ongoing",
        action="store_true",
        help="markera händelsen som pågående i stället för tidsbegränsad",
    )
    note_add_parser.add_argument(
        "note",
        help="kort privat beskrivning; citeras om den innehåller mellanslag",
    )
    note_add_parser.set_defaults(handler=run_note_add)

    note_list_parser = note_subparsers.add_parser(
        "list",
        help="visa sparade context-noter",
    )
    note_list_parser.add_argument(
        "--from",
        dest="start_date",
        type=iso_date,
        help="första datum i ett överlappande filter, YYYY-MM-DD",
    )
    note_list_parser.add_argument(
        "--to",
        dest="end_date",
        type=iso_date,
        help="sista datum i ett överlappande filter, YYYY-MM-DD",
    )
    note_list_parser.set_defaults(handler=run_note_list)

    metrics_parser = subparsers.add_parser(
        "metrics",
        help="beräkna deterministiska tränings- och recovery-mått",
    )
    metrics_subparsers = metrics_parser.add_subparsers(dest="metrics_command")
    metrics_summary_parser = metrics_subparsers.add_parser(
        "summary",
        help="visa fakta för träning och recovery",
    )
    metrics_summary_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="sista datum i analysen, YYYY-MM-DD (standard: idag)",
    )
    metrics_summary_parser.set_defaults(handler=run_metrics_summary)

    state_parser = subparsers.add_parser(
        "state",
        help="visa ett lokalt snapshot av fakta, kontext och datakvalitet",
    )
    state_subparsers = state_parser.add_subparsers(dest="state_command")
    state_show_parser = state_subparsers.add_parser(
        "show",
        help="visa athlete state utan coachingtolkning",
    )
    state_show_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="sista datum i state-fönstret, YYYY-MM-DD (standard: idag)",
    )
    state_show_parser.set_defaults(handler=run_state_show)

    rules_parser = subparsers.add_parser(
        "rules",
        help="utvärdera transparenta Pace-regler utan coachingråd",
    )
    rules_subparsers = rules_parser.add_subparsers(dest="rules_command")
    rules_evaluate_parser = rules_subparsers.add_parser(
        "evaluate",
        help="visa strukturerade regelresultat",
    )
    rules_evaluate_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="sista datum i regelutvärderingen, YYYY-MM-DD (standard: idag)",
    )
    rules_evaluate_parser.set_defaults(handler=run_rules_evaluate)

    explain_parser = subparsers.add_parser(
        "explain",
        help="förklara Pace-regler med lokala, deterministiska mallar",
    )
    explain_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="sista datum i förklaringen, YYYY-MM-DD (standard: idag)",
    )
    explain_parser.set_defaults(handler=run_explain)

    ask_parser = subparsers.add_parser(
        "ask",
        help="fråga AI-assistenten om valda, lokala Pace-fakta",
    )
    ask_parser.add_argument(
        "question",
        help="en frivillig fråga; varje fråga behandlas separat",
    )
    ask_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="sista datum i faktaunderlaget, YYYY-MM-DD (standard: idag)",
    )
    ask_parser.set_defaults(handler=run_ask)

    knowledge_parser = subparsers.add_parser(
        "knowledge",
        help="visa Paces lokala, kuraterade kunskapsunderlag utan nätverksanrop",
    )
    knowledge_subparsers = knowledge_parser.add_subparsers(dest="knowledge_command")
    knowledge_list_parser = knowledge_subparsers.add_parser(
        "list", help="lista tillgängliga kunskapsbriefs"
    )
    knowledge_list_parser.set_defaults(handler=run_knowledge_list)
    knowledge_show_parser = knowledge_subparsers.add_parser(
        "show", help="visa en brief, dess begränsningar och källor"
    )
    knowledge_show_parser.add_argument("--id", dest="brief_id", required=True)
    knowledge_show_parser.set_defaults(handler=run_knowledge_show)

    coach_parser = subparsers.add_parser(
        "coach",
        help="diskutera dagens accepterade plan med AI-coachen utan att ändra den",
    )
    coach_subparsers = coach_parser.add_subparsers(dest="coach_command")
    coach_ask_parser = coach_subparsers.add_parser(
        "ask", help="ställ en snabb fråga om dagens accepterade plan"
    )
    coach_ask_parser.add_argument("question")
    coach_ask_parser.add_argument("--plan-id", type=int, required=True)
    coach_ask_parser.add_argument("--end-date", type=iso_date)
    coach_ask_parser.set_defaults(handler=run_coach_ask)
    coach_chat_parser = coach_subparsers.add_parser(
        "chat", help="öppna en kortlivad coachdialog för dagens accepterade plan"
    )
    coach_chat_parser.add_argument("--plan-id", type=int, required=True)
    coach_chat_parser.add_argument("--end-date", type=iso_date)
    coach_chat_parser.set_defaults(handler=run_coach_chat)

    race_parser = subparsers.add_parser(
        "race",
        help="hantera kommande lopp för framtida planering",
    )
    race_subparsers = race_parser.add_subparsers(dest="race_command")
    race_add_parser = race_subparsers.add_parser(
        "add",
        help="spara ett kommande A-, B- eller C-lopp",
    )
    race_add_parser.add_argument("name", help="loppets namn")
    race_add_parser.add_argument("--date", type=iso_date, required=True)
    race_add_parser.add_argument(
        "--sport",
        choices=sorted(SUPPORTED_RACE_SPORT_TYPES),
        required=True,
    )
    race_add_parser.add_argument(
        "--distance-km",
        type=positive_distance_km,
        required=True,
    )
    race_add_parser.add_argument(
        "--priority",
        choices=sorted(SUPPORTED_RACE_PRIORITIES),
        required=True,
        help="A = huvudmål, B = delmål, C = hårt träningspass",
    )
    race_add_parser.add_argument(
        "--desired-time",
        type=duration_seconds,
        help="önskad tid H:MM:SS; ett mål, inte ett kapacitetsbevis",
    )
    race_add_parser.add_argument(
        "--taper",
        choices=sorted(SUPPORTED_TAPER_CHOICES),
        help="skriv över A/B/C-standard för just detta lopp",
    )
    race_add_parser.set_defaults(handler=run_race_add)

    race_list_parser = race_subparsers.add_parser(
        "list",
        help="visa kommande lopp och deras taper-policy",
    )
    race_list_parser.add_argument(
        "--as-of-date",
        type=iso_date,
        help="visa lopp från detta datum, YYYY-MM-DD (standard: idag)",
    )
    race_list_parser.add_argument(
        "--include-past",
        action="store_true",
        help="inkludera historiska lopp, exempelvis för att länka ett Garmin-resultat",
    )
    race_list_parser.add_argument(
        "--include-cancelled",
        action="store_true",
        help="inkludera avbrutna framtida lopp i listan",
    )
    race_list_parser.set_defaults(handler=run_race_list)

    race_update_parser = race_subparsers.add_parser(
        "update",
        help="rätta ett oanvänt lopp eller ändra dess prioritet/taper",
    )
    race_update_parser.add_argument("--id", type=int, required=True)
    race_update_parser.add_argument("--name")
    race_update_parser.add_argument("--date", type=iso_date)
    race_update_parser.add_argument("--sport", choices=sorted(SUPPORTED_RACE_SPORT_TYPES))
    race_update_parser.add_argument("--distance-km", type=positive_distance_km)
    race_update_parser.add_argument("--desired-time", type=duration_seconds)
    race_update_parser.add_argument("--clear-desired-time", action="store_true")
    race_update_parser.add_argument(
        "--priority",
        choices=sorted(SUPPORTED_RACE_PRIORITIES),
    )
    race_update_parser.add_argument(
        "--taper",
        choices=sorted(SUPPORTED_TAPER_CHOICES),
    )
    race_update_parser.set_defaults(handler=run_race_update)

    race_remove_parser = race_subparsers.add_parser(
        "remove", help="ta bort ett oanvänt framtida lopp permanent"
    )
    race_remove_parser.add_argument("--id", type=int, required=True)
    race_remove_parser.set_defaults(handler=run_race_remove)
    race_cancel_parser = race_subparsers.add_parser(
        "cancel", help="avbryt ett framtida lopp utan att radera historik"
    )
    race_cancel_parser.add_argument("--id", type=int, required=True)
    race_cancel_parser.set_defaults(handler=run_race_cancel)

    plan_parser = subparsers.add_parser(
        "plan",
        help="skapa, granska och följa lokala Pace-planer",
    )
    plan_subparsers = plan_parser.add_subparsers(dest="plan_command")
    plan_readiness_parser = plan_subparsers.add_parser(
        "readiness",
        help="kontrollera Garmin-historik, aktiva hälsoblockerare och lopp",
    )
    plan_readiness_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="planeringsdatum YYYY-MM-DD (standard: idag)",
    )
    plan_readiness_parser.set_defaults(handler=run_plan_readiness)

    plan_checkpoint_parser = plan_subparsers.add_parser(
        "checkpoint",
        help="visa när nästa explicita planrevision behövs och vilka lopp som närmar sig",
    )
    plan_checkpoint_parser.add_argument("--end-date", type=iso_date)
    plan_checkpoint_parser.set_defaults(handler=run_plan_checkpoint)

    plan_draft_parser = plan_subparsers.add_parser(
        "draft",
        help="skapa och aktivera en validerad AI-genererad plan",
    )
    plan_draft_parser.add_argument(
        "--race-id",
        type=int,
        help="valfritt aktivt lopp som definierar blocket; utan lopp används allmänt mål",
    )
    plan_draft_parser.add_argument(
        "--days",
        type=plan_days,
        default=14,
        help="antal detaljerade dagar, 7 eller 14 (standard: 14)",
    )
    plan_draft_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="planeringsdatum YYYY-MM-DD (standard: idag)",
    )
    plan_draft_parser.set_defaults(handler=run_plan_draft)

    plan_list_parser = plan_subparsers.add_parser(
        "list",
        help="visa lokala planer och tidigare versioner",
    )
    plan_list_parser.set_defaults(handler=run_plan_list)

    plan_show_parser = plan_subparsers.add_parser(
        "show",
        help="visa en lokal planversion",
    )
    plan_show_parser.add_argument("--id", type=int, required=True)
    plan_show_parser.set_defaults(handler=run_plan_show)

    plan_today_parser = plan_subparsers.add_parser(
        "today",
        help="visa dagens eller nästa pass i läsbart format",
    )
    plan_today_parser.add_argument(
        "--id",
        type=int,
        help="valfritt plan-id; krävs för att förhandsvisa ett utkast",
    )
    plan_today_parser.add_argument(
        "--date",
        type=iso_date,
        help="datum YYYY-MM-DD (standard: idag)",
    )
    plan_today_parser.set_defaults(handler=run_plan_today)

    plan_review_parser = plan_subparsers.add_parser(
        "review",
        help="visa en plan, coachbedömning och utfall i läsbart format",
    )
    plan_review_parser.add_argument("--id", type=int, required=True)
    plan_review_parser.set_defaults(handler=run_plan_review)

    plan_report_parser = plan_subparsers.add_parser(
        "report",
        help="skapa en privat HTML-rapport för en lokal plan",
    )
    plan_report_parser.add_argument("--id", type=int, required=True)
    plan_report_parser.set_defaults(handler=run_plan_report)

    plan_accept_parser = plan_subparsers.add_parser(
        "accept",
        help="acceptera ett äldre legacy-utkast utan att radera planversioner",
    )
    plan_accept_parser.add_argument("--id", type=int, required=True)
    plan_accept_parser.set_defaults(handler=run_plan_accept)

    plan_feedback_parser = plan_subparsers.add_parser(
        "feedback",
        help="spara ett strukturerat utfall för ett accepterat pass",
    )
    plan_feedback_parser.add_argument("--session-id", type=int, required=True)
    plan_feedback_parser.add_argument(
        "--outcome", choices=sorted(SUPPORTED_FEEDBACK_OUTCOMES), required=True
    )
    plan_feedback_parser.add_argument(
        "--rpe",
        type=feedback_rpe,
        help="valfri upplevd ansträngning 1–10; används bara för genomförda pass",
    )
    plan_feedback_parser.add_argument(
        "--reason",
        choices=sorted(SUPPORTED_FEEDBACK_REASON_CODES),
        help="valfri strukturerad orsak för begränsat eller missat pass",
    )
    plan_feedback_parser.add_argument("--note", help="valfri lokal notering")
    plan_feedback_parser.add_argument(
        "--share-note-with-ai",
        action="store_true",
        help="tillåt att just denna notering skickas i ett framtida revisionsutkast",
    )
    plan_feedback_parser.set_defaults(handler=run_plan_feedback)

    plan_workout_parser = plan_subparsers.add_parser(
        "workout",
        help="granska ett planerat pass mot explicit feedback och samma dags Garmin-data",
    )
    plan_workout_subparsers = plan_workout_parser.add_subparsers(dest="plan_workout_command")
    plan_workout_evaluate_parser = plan_workout_subparsers.add_parser(
        "evaluate",
        help="utvärdera utan att ändra plan eller registrera genomförande automatiskt",
    )
    plan_workout_evaluate_parser.add_argument("--session-id", type=int, required=True)
    plan_workout_evaluate_parser.set_defaults(handler=run_plan_workout_evaluate)

    plan_revise_parser = plan_subparsers.add_parser(
        "revise",
        help="skapa och aktivera en kort reviderad plan efter validering",
    )
    plan_revise_parser.add_argument("--id", type=int, required=True)
    plan_revise_parser.add_argument("--days", type=plan_days, default=14)
    plan_revise_parser.add_argument("--end-date", type=iso_date)
    plan_revise_parser.set_defaults(handler=run_plan_revise)

    trends_parser = subparsers.add_parser(
        "trends",
        help="visa lokala trender från uttryckligen registrerad passåterkoppling",
    )
    trends_subparsers = trends_parser.add_subparsers(dest="trends_command")
    trends_show_parser = trends_subparsers.add_parser(
        "show", help="visa två 28-dagarsfönster utan att ändra någon plan"
    )
    trends_show_parser.add_argument(
        "--end-date", type=iso_date, help="slutdatum YYYY-MM-DD (standard: idag)"
    )
    trends_show_parser.set_defaults(handler=run_trends_show)

    analysis_parser = subparsers.add_parser(
        "analysis",
        help="visa transparenta träningsfakta utan ett dolt belastningsscore",
    )
    analysis_subparsers = analysis_parser.add_subparsers(dest="analysis_command")
    analysis_show_parser = analysis_subparsers.add_parser(
        "show",
        help="visa ett lokalt 28-dagarsfönster för träning, feedback och datatäckning",
    )
    analysis_show_parser.add_argument(
        "--end-date", type=iso_date, help="slutdatum YYYY-MM-DD (standard: idag)"
    )
    analysis_show_parser.set_defaults(handler=run_analysis_show)

    dashboard_parser = subparsers.add_parser(
        "dashboard", help="skapa en lokal, informationstät HTML-dashboard"
    )
    dashboard_parser.add_argument(
        "--end-date", type=iso_date, help="datum YYYY-MM-DD (standard: idag)"
    )
    dashboard_parser.set_defaults(handler=run_dashboard)

    home_parser = subparsers.add_parser(
        "home", help="skapa en central lokal HTML-startsida för Pace"
    )
    home_parser.add_argument(
        "--end-date", type=iso_date, help="datum YYYY-MM-DD (standard: idag)"
    )
    home_parser.set_defaults(handler=run_home)

    serve_parser = subparsers.add_parser(
        "serve",
        help="starta Pace Home som en privat lokal browser-app",
    )
    serve_parser.add_argument(
        "--port",
        type=local_port,
        default=8765,
        help="lokal port på 127.0.0.1 (standard: 8765)",
    )
    serve_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="öppna inte webbläsaren automatiskt",
    )
    serve_parser.set_defaults(handler=run_serve)

    eval_parser = subparsers.add_parser(
        "eval", help="granska Paces coachkontrakt med syntetiska scenarier"
    )
    eval_subparsers = eval_parser.add_subparsers(dest="eval_command")
    eval_scenarios_parser = eval_subparsers.add_parser(
        "scenarios", help="lista den lokala, nätverksfria coach-testkatalogen"
    )
    eval_scenarios_parser.set_defaults(handler=run_eval_scenarios)
    eval_coach_parser = eval_subparsers.add_parser(
        "coach", help="kör ett uttryckligt live-AI-test mot syntetiska fakta"
    )
    eval_coach_parser.add_argument(
        "--live",
        action="store_true",
        help="bekräfta sex OpenAI-anrop; ingen riktig atletdata används",
    )
    eval_coach_parser.set_defaults(handler=run_eval_coach)

    review_parser = subparsers.add_parser("review", help="skapa en explicit AI-veckoreview som lokal HTML")
    review_subparsers = review_parser.add_subparsers(dest="review_command")
    weekly_review_parser = review_subparsers.add_parser("weekly", help="analysera senaste veckan utan att ändra plan")
    weekly_review_parser.add_argument("--end-date", type=iso_date)
    weekly_review_parser.set_defaults(handler=run_weekly_review)

    profile_parser = subparsers.add_parser("profile", help="hantera bekräftade personliga coachprinciper")
    profile_subparsers = profile_parser.add_subparsers(dest="profile_command")
    profile_list_parser = profile_subparsers.add_parser("list", help="visa aktiva och granskningsförfallna principer")
    profile_list_parser.add_argument("--end-date", type=iso_date)
    profile_list_parser.set_defaults(handler=run_profile_list)
    profile_accept_parser = profile_subparsers.add_parser("accept", help="bekräfta en coachprincip från ett planutkast")
    profile_accept_parser.add_argument("--plan-id", type=int, required=True)
    profile_accept_parser.add_argument("--principle-index", type=int, required=True)
    profile_accept_parser.add_argument("--end-date", type=iso_date)
    profile_accept_parser.set_defaults(handler=run_profile_accept)
    profile_archive_parser = profile_subparsers.add_parser("archive", help="arkivera en bekräftad coachprincip")
    profile_archive_parser.add_argument("--id", type=int, required=True)
    profile_archive_parser.set_defaults(handler=run_profile_archive)

    preferences_parser = subparsers.add_parser(
        "preferences",
        help="hantera tillgänglighet och sportroll för framtida planutkast",
    )
    preferences_subparsers = preferences_parser.add_subparsers(dest="preferences_command")
    preferences_set_parser = preferences_subparsers.add_parser(
        "set", help="spara tillgängliga dagar och önskad sportroll"
    )
    preferences_set_parser.add_argument(
        "--sport-role", choices=sorted(SUPPORTED_SPORT_ROLES), required=True
    )
    preferences_set_parser.add_argument(
        "--ambition",
        choices=sorted(SUPPORTED_COACHING_AMBITIONS),
        help=(
            "cautious = större marginaler, balanced = standard, "
            "ambitious = mer offensivt utkast när fakta stödjer det"
        ),
    )
    preferences_set_parser.add_argument(
        "--day",
        action="append",
        required=True,
        help="tillgänglighet som mon:60 eller mon:any; upprepa för flera dagar",
    )
    preferences_set_parser.set_defaults(handler=run_preferences_set)
    preferences_show_parser = preferences_subparsers.add_parser(
        "show", help="visa sparad tillgänglighet och sportroll"
    )
    preferences_show_parser.set_defaults(handler=run_preferences_show)
    preferences_ambition_parser = preferences_subparsers.add_parser(
        "ambition", help="ändra ambitionsläge utan att skriva om tillgängliga dagar"
    )
    preferences_ambition_parser.add_argument(
        "--ambition", choices=sorted(SUPPORTED_COACHING_AMBITIONS), required=True
    )
    preferences_ambition_parser.set_defaults(handler=run_preferences_ambition)

    zones_parser = subparsers.add_parser(
        "zones",
        help="spara och visa manuellt bekräftade Garmin-pulszoner för cykling",
    )
    zones_subparsers = zones_parser.add_subparsers(dest="zones_command")
    zones_set_parser = zones_subparsers.add_parser(
        "set", help="spara fem Garmin-pulszoner för cykling"
    )
    zones_set_parser.add_argument("--sport", choices=["ride"], required=True)
    zones_set_parser.add_argument(
        "--zone",
        action="append",
        required=True,
        help="Garmin-zon som 1:100-120; ange exakt fem gånger för Z1–Z5",
    )
    zones_set_parser.set_defaults(handler=run_zones_set)
    zones_show_parser = zones_subparsers.add_parser(
        "show", help="visa sparade Garmin-pulszoner"
    )
    zones_show_parser.add_argument("--sport", choices=["ride"], default="ride")
    zones_show_parser.set_defaults(handler=run_zones_show)

    capacity_parser = subparsers.add_parser(
        "capacity",
        help="visa deterministiska fakta om faktisk träningskapacitet",
    )
    capacity_subparsers = capacity_parser.add_subparsers(dest="capacity_command")
    capacity_show_parser = capacity_subparsers.add_parser(
        "show",
        help="visa volym, kontinuitet, sportbalans och datakvalitet",
    )
    capacity_show_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="analysdatum YYYY-MM-DD (standard: idag)",
    )
    capacity_show_parser.set_defaults(handler=run_capacity_show)

    performance_parser = subparsers.add_parser(
        "performance",
        help="hantera begränsade Garmin-detaljer och verifierbara loppresultat",
    )
    performance_subparsers = performance_parser.add_subparsers(
        dest="performance_command"
    )
    performance_sync_parser = performance_subparsers.add_parser(
        "sync",
        help="hämta lokala run/ride-detaljer och splits för en sjudagarsbatch",
    )
    performance_sync_parser.add_argument(
        "--days",
        type=positive_days,
        default=7,
        help="antal kalenderdagar inklusive batchens slutdatum (standard: 7)",
    )
    performance_sync_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="sista datum i batchen, YYYY-MM-DD (standard: idag)",
    )
    performance_sync_parser.set_defaults(handler=run_performance_sync)

    performance_show_parser = performance_subparsers.add_parser(
        "show",
        help="visa tolv veckors detaljtäckning och explicit länkade loppresultat",
    )
    performance_show_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="sista datum i analysen, YYYY-MM-DD (standard: idag)",
    )
    performance_show_parser.set_defaults(handler=run_performance_show)

    performance_link_race_parser = performance_subparsers.add_parser(
        "link-race",
        help="länka ett bekräftat lopp till en detaljerad Garmin-aktivitet",
    )
    performance_link_race_parser.add_argument(
        "--garmin-activity-id",
        required=True,
        help="Garmin-id från 'pace performance show'",
    )
    performance_link_race_parser.add_argument(
        "--race-id",
        type=int,
        required=True,
        help="lokalt lopp-id från 'pace race list --include-past'",
    )
    performance_link_race_parser.set_defaults(handler=run_performance_link_race)

    performance_benchmark_parser = performance_subparsers.add_parser(
        "mark-benchmark",
        help="markera ett genomfört Pace-definierat benchmark-pass",
    )
    performance_benchmark_parser.add_argument(
        "--garmin-activity-id",
        required=True,
        help="Garmin-id från 'pace performance show'",
    )
    performance_benchmark_parser.add_argument(
        "--protocol",
        choices=sorted(SUPPORTED_BENCHMARK_PROTOCOLS),
        required=True,
        help="Pace-protokollet som aktiviteten måste uppfylla",
    )
    performance_benchmark_parser.set_defaults(handler=run_performance_mark_benchmark)

    performance_readiness_parser = performance_subparsers.add_parser(
        "readiness",
        help="kontrollera om evidence och aktuell sporthistorik räcker för intensitetsmål",
    )
    performance_readiness_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="analysdatum YYYY-MM-DD (standard: idag)",
    )
    performance_readiness_parser.set_defaults(handler=run_performance_readiness)

    return parser


def run_db_init(_args: Namespace) -> int:
    """Apply every reviewed Alembic migration to Pace's local database."""

    try:
        initialize_database(database_url=settings.database_url)
    except Exception:
        print("Databasen kunde inte initieras eller uppgraderas.")
        return 1

    print("Pace-databasen är initierad och uppgraderad till senaste schema.")
    return 0


def run_garmin_login(args: Namespace) -> int:
    """Prompt for credentials once and let the Garmin library save a session."""

    email = args.email or input("Garmin-e-post: ").strip()
    password = getpass("Garmin-lösenord: ")

    if not email or not password:
        print("Inloggningen avbröts: e-post och lösenord måste anges.")
        return 2

    try:
        GarminConnectClient.login_with_credentials(
            email=email,
            password=password,
            token_dir=settings.garmin_token_dir,
            prompt_mfa=lambda: getpass("Garmin MFA-kod: ").strip(),
        )
    except GarminRateLimitError as error:
        print(f"Garmin-inloggningen stoppades: {error}")
        return 3
    except GarminIntegrationError as error:
        print(f"Garmin-inloggningen misslyckades: {error}")
        return 2

    print(
        "Garmin är anslutet. En lokal session har sparats i "
        f"{settings.garmin_token_dir}."
    )
    return 0


def run_sync(args: Namespace, *, today: date | None = None) -> int:
    """Synchronize a bounded activity and recovery window."""

    sync_end_date = getattr(args, "end_date", None) or today or date.today()
    sync_start_date = sync_end_date - timedelta(days=args.days - 1)

    try:
        client = GarminConnectClient.from_saved_tokens(settings.garmin_token_dir)
        result = GarminSyncService(client).sync(
            start_date=sync_start_date,
            end_date=sync_end_date,
        )
    except GarminAuthenticationRequiredError as error:
        print(f"Synken kan inte starta: {error}")
        return 2
    except GarminRateLimitError as error:
        print(f"Synken stoppades: {error}")
        return 3
    except GarminIntegrationError as error:
        print(f"Synken misslyckades: {error}")
        return 2
    except Exception:
        print("Synken misslyckades. Databasen lämnades oförändrad för denna synk.")
        return 1

    print(
        f"Garmin-synk klar ({result.start_date} till {result.end_date}): "
        f"{result.activities_fetched} hämtade, "
        f"{result.activities_inserted} nya, "
        f"{result.activities_updated} uppdaterade aktiviteter; "
        f"{result.daily_metrics_fetched} recovery-dagar, "
        f"{result.daily_metrics_inserted} nya och "
        f"{result.daily_metrics_updated} uppdaterade recovery-poster."
    )

    if result.status == "partial":
        if result.recovery_stop_reason == "rate_limit":
            print(
                "Recovery-datan hämtades delvis eftersom Garmin begränsade "
                "förfrågningarna. Tillgängliga värden sparades; vänta och kör "
                "samma batch igen senare."
            )
            return 3
        if result.recovery_stop_reason == "authentication":
            print(
                "Recovery-datan hämtades delvis eftersom Garmin-sessionen "
                "slutade vara giltig. Tillgängliga värden sparades; kör "
                "'pace garmin login' och därefter samma batch igen."
            )
            return 2

        print(
            "Recovery-datan hämtades delvis. Aktiviteter och tillgängliga "
            "recovery-värden sparades; kör samma batch igen senare för resten."
        )

    return 0


def run_note_add(args: Namespace) -> int:
    """Store one athlete-provided context fact without interpreting it."""

    try:
        event = ContextService().add_event(
            ContextEventInput(
                event_type=args.event_type,
                start_date=args.start_date,
                end_date=args.end_date,
                ongoing=args.ongoing,
                note=args.note,
            )
        )
    except ValueError as error:
        print(f"Context-noten kunde inte sparas: {error}")
        return 2

    duration = "pågående" if event.end_date is None else str(event.end_date)
    print(f"Context-not sparad: {event.event_type}, från {event.start_date} till {duration}.")
    return 0


def run_note_list(args: Namespace) -> int:
    """Print local context events as structured data requested by the athlete."""

    try:
        events = ContextService().list_events(
            start_date=args.start_date,
            end_date=args.end_date,
        )
    except ValueError as error:
        print(f"Context-noter kunde inte hämtas: {error}")
        return 2

    print(json.dumps([asdict(event) for event in events], default=_json_default, indent=2))
    return 0


def _json_default(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Kan inte serialisera {type(value).__name__} till JSON.")


def run_metrics_summary(args: Namespace, *, today: date | None = None) -> int:
    """Print a reproducible, structured factual summary from local Pace data."""

    end_date = args.end_date or today or date.today()
    summary = MetricService().get_summary(end_date=end_date)
    print(json.dumps(asdict(summary), default=_json_default, indent=2))
    return 0


def run_state_show(args: Namespace, *, today: date | None = None) -> int:
    """Print a local athlete snapshot without external calls or interpretation."""

    end_date = args.end_date or today or date.today()
    athlete_state = AthleteStateService().get_state(end_date=end_date)
    print(json.dumps(asdict(athlete_state), default=_json_default, indent=2))
    return 0


def run_rules_evaluate(args: Namespace, *, today: date | None = None) -> int:
    """Print structured deterministic rule outcomes without prose or advice."""

    end_date = args.end_date or today or date.today()
    summary = RuleService().evaluate(end_date=end_date)
    print(json.dumps(asdict(summary), default=_json_default, indent=2))
    return 0


def run_explain(args: Namespace, *, today: date | None = None) -> int:
    """Print readable deterministic explanations without external calls or advice."""

    end_date = args.end_date or today or date.today()
    explanation = ExplanationService().explain(end_date=end_date)
    print(render_explanation_summary(explanation))
    return 0


def run_ask(args: Namespace, *, today: date | None = None) -> int:
    """Ask for an AI explanation without writing Pace state or context."""

    question = args.question.strip()
    if not question:
        print("Frågan kan inte vara tom.")
        return 2
    try:
        openai_api_key = resolve_openai_api_key(settings)
    except ValueError as error:
        print(f"AI-assistenten är inte konfigurerad: {error}")
        return 2
    if not openai_api_key:
        print(
            "AI-assistenten är inte konfigurerad. Sätt OPENAI_API_KEY lokalt och "
            "kör samma kommando igen. Ingen Pace-data har skickats."
        )
        return 2

    end_date = args.end_date or today or date.today()
    try:
        answer = PaceAskService(
            client=OpenAIResponsesClient(
                api_key=openai_api_key,
                model=settings.openai_model,
            )
        ).ask(question=question, end_date=end_date)
    except PaceAIError as error:
        print(str(error))
        return 1

    print(_render_ai_answer(answer, as_of_date=end_date))
    return 0


def run_knowledge_list(_args: Namespace) -> int:
    """List the checked-in knowledge briefs without fetching any source."""

    try:
        library = load_knowledge_library()
    except KnowledgeLibraryError as error:
        print(f"Kunskapsbiblioteket kunde inte läsas: {error}")
        return 2
    print("Paces lokala kunskapsbriefs")
    for brief in library.briefs:
        print(f"- {brief.id}: {brief.title} ({', '.join(brief.topic_tags)})")
    print("Visar lokala, granskade sammanfattningar. Inget har hämtats från nätet.")
    return 0


def run_knowledge_show(args: Namespace) -> int:
    """Render one local brief with its claims, limits, and source links."""

    try:
        library = load_knowledge_library()
    except KnowledgeLibraryError as error:
        print(f"Kunskapsbiblioteket kunde inte läsas: {error}")
        return 2
    brief = brief_by_id(library, brief_id=args.brief_id)
    if brief is None:
        print(f"Ingen kunskapsbrief har id '{args.brief_id}'. Kör 'pace knowledge list'.")
        return 2
    lines = [brief.title, f"ID: {brief.id}", "", "Stödjer:"]
    lines.extend(f"- {claim}" for claim in brief.supported_claims)
    lines.extend(["", "Begränsningar:"])
    lines.extend(f"- {limitation}" for limitation in brief.limitations)
    lines.extend(["", "När Pace får använda den:", f"- {brief.applicability}", "", "Källor:"])
    for source_id in brief.source_ids:
        source = source_by_id(library, source_id=source_id)
        if source is not None:
            lines.append(
                f"- {source.authors} ({source.publication_year}). {source.title}. "
                f"{source.evidence_type}. {source.url}"
            )
    print("\n".join(lines))
    return 0


def _coach_dialogue_service() -> CoachDialogueService:
    api_key = resolve_openai_api_key(settings)
    if not api_key:
        raise ValueError("OPENAI_API_KEY saknas; coachdialogen kan inte startas.")
    return CoachDialogueService(
        client=OpenAICoachDialogueClient(api_key=api_key, model=settings.openai_model)
    )


def run_coach_ask(args: Namespace, *, today: date | None = None) -> int:
    """Ask once about an accepted plan; an adjustment remains only a draft."""

    end_date = args.end_date or today or date.today()
    try:
        plan = TrainingPlanService().get_plan(plan_id=args.plan_id)
        answer = _coach_dialogue_service().ask(
            question=args.question,
            plan=plan,
            end_date=end_date,
        )
    except (ValueError, PaceAIError) as error:
        print(f"Coachdialogen kunde inte genomföras: {error}")
        return 2
    print(_render_coach_answer(answer, plan_id=plan.id, as_of_date=end_date))
    return 0


def run_coach_chat(args: Namespace, *, today: date | None = None) -> int:
    """Run a local-memory-only multi-turn dialogue over one accepted plan."""

    end_date = args.end_date or today or date.today()
    try:
        plan = TrainingPlanService().get_plan(plan_id=args.plan_id)
        service = _coach_dialogue_service()
        if plan.status != "accepted":
            raise ValueError("Coachdialog requires an accepted plan.")
    except (ValueError, PaceAIError) as error:
        print(f"Coachdialogen kunde inte startas: {error}")
        return 2
    print(
        f"Pace coach ({end_date}) för accepterad plan {plan.id}. "
        "Skriv 'avsluta' för att stänga. Dialogen sparas inte."
    )
    conversation: tuple[dict[str, str], ...] = ()
    while True:
        try:
            question = input("Du: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCoachdialogen avslutad. Inget sparades.")
            return 0
        if question.casefold() in {"avsluta", "exit", "quit"}:
            print("Coachdialogen avslutad. Inget sparades.")
            return 0
        if not question:
            continue
        try:
            answer = service.ask(
                question=question,
                plan=plan,
                end_date=end_date,
                conversation=conversation,
            )
        except (ValueError, PaceAIError) as error:
            print(f"Coachdialogen kunde inte svara: {error}")
            continue
        print(_render_coach_answer(answer, plan_id=plan.id, as_of_date=end_date))
        conversation = (
            *conversation,
            {"role": "athlete", "text": question},
            {"role": "coach", "text": answer.answer},
        )[-8:]


def run_race_add(args: Namespace) -> int:
    """Persist one athlete-confirmed race without generating a plan."""

    try:
        race = RaceService().add_race(
            RaceInput(
                name=args.name,
                sport_type=args.sport,
                race_date=args.date,
                distance_meters=args.distance_km * 1000,
                priority=args.priority,
                desired_time_seconds=args.desired_time,
                taper_override=args.taper,
            )
        )
    except ValueError as error:
        print(f"Loppet kunde inte sparas: {error}")
        return 2

    print(
        f"Lopp sparat: {race.name} ({race.race_date}), prioritet {race.priority}, "
        f"taper {resolved_taper(race)}."
    )
    return 0


def run_race_list(args: Namespace, *, today: date | None = None) -> int:
    """Print future race facts without assessing race readiness or capacity."""

    as_of_date = args.as_of_date or today or date.today()
    races = RaceService().list_races(
        as_of_date=as_of_date,
        include_past=getattr(args, "include_past", False),
        include_cancelled=getattr(args, "include_cancelled", False),
    )
    payload = [
        {
            "id": race.id,
            "name": race.name,
            "sport_type": race.sport_type,
            "race_date": race.race_date,
            "distance_meters": race.distance_meters,
            "priority": race.priority,
            "desired_time_seconds": race.desired_time_seconds,
            "taper_override": race.taper_override,
            "taper": resolved_taper(race),
            "status": race.status,
        }
        for race in races
    ]
    print(json.dumps(payload, default=_json_default, indent=2))
    return 0


def run_race_update(args: Namespace) -> int:
    """Correct an unused race, preserving any linked plan/result history."""

    try:
        race = RaceService().update_race(
            race_id=args.id,
            name=args.name,
            sport_type=args.sport,
            race_date=args.date,
            distance_meters=(
                None if args.distance_km is None else args.distance_km * 1000
            ),
            desired_time_seconds=args.desired_time,
            clear_desired_time=args.clear_desired_time,
            priority=args.priority,
            taper_override=args.taper,
        )
    except ValueError as error:
        print(f"Loppet kunde inte uppdateras: {error}")
        return 2

    print(
        f"Lopp uppdaterat: {race.name} ({race.race_date}), prioritet "
        f"{race.priority}, taper {resolved_taper(race)}."
    )
    return 0


def run_race_remove(args: Namespace, *, today: date | None = None) -> int:
    try:
        RaceService().remove_race(race_id=args.id, as_of_date=today or date.today())
    except ValueError as error:
        print(f"Loppet kunde inte tas bort: {error}")
        return 2
    print("Loppet är borttaget. Inga planer eller Garmin-resultat påverkades.")
    return 0


def run_race_cancel(args: Namespace, *, today: date | None = None) -> int:
    try:
        race = RaceService().cancel_race(race_id=args.id, as_of_date=today or date.today())
    except ValueError as error:
        print(f"Loppet kunde inte avbrytas: {error}")
        return 2
    print(f"Loppet är avbrutet: {race.name}. Det används inte i ny planering.")
    return 0


def run_plan_readiness(args: Namespace, *, today: date | None = None) -> int:
    """Print deterministic planning gates without generating a plan."""

    end_date = args.end_date or today or date.today()
    readiness = PlanReadinessService().get_readiness(as_of_date=end_date)
    print(json.dumps(asdict(readiness), default=_json_default, indent=2))
    return 0


def run_plan_checkpoint(args: Namespace, *, today: date | None = None) -> int:
    checkpoint = PlanCheckpointService().get_checkpoint(
        as_of_date=args.end_date or today or date.today()
    )
    print(json.dumps(asdict(checkpoint), default=_json_default, indent=2))
    return 0


def run_preferences_set(args: Namespace) -> int:
    try:
        preference = TrainingPreferenceService().set_preference(
            TrainingPreferenceInput(
                sport_role=args.sport_role,
                available_days=tuple(args.day),
                coaching_ambition=args.ambition,
            )
        )
    except ValueError as error:
        print(f"Planpreferenserna kunde inte sparas: {error}")
        return 2
    print(
        f"Planpreferenser sparade: {preference.sport_role}, "
        f"ambition {preference.coaching_ambition}, "
        f"{len(preference.available_days)} tillgängliga dagar."
    )
    return 0


def run_preferences_show(_args: Namespace) -> int:
    preference = TrainingPreferenceService().get_preference()
    if preference is None:
        print("Inga planpreferenser är sparade ännu.")
        return 2
    print(
        json.dumps(
            {
                "sport_role": preference.sport_role,
                "coaching_ambition": preference.coaching_ambition,
                "available_days": preference.available_days,
            },
            indent=2,
        )
    )
    return 0


def run_preferences_ambition(args: Namespace) -> int:
    try:
        preference = TrainingPreferenceService().set_coaching_ambition(
            coaching_ambition=args.ambition
        )
    except ValueError as error:
        print(f"Ambitionsläget kunde inte sparas: {error}")
        return 2
    print(f"Ambitionsläge sparat: {preference.coaching_ambition}.")
    return 0


def run_zones_set(args: Namespace) -> int:
    try:
        profile = HeartRateZoneService().set_profile(
            HeartRateZoneInput(sport_type=args.sport, zones=tuple(args.zone))
        )
    except ValueError as error:
        print(f"Garmin-pulszonerna kunde inte sparas: {error}")
        return 2
    print("Garmin-pulszoner för cykling är sparade lokalt.")
    print(json.dumps({"sport_type": profile.sport_type, "zones": profile.zones}, indent=2))
    return 0


def run_zones_show(args: Namespace) -> int:
    profile = HeartRateZoneService().get_profile(sport_type=args.sport)
    if profile is None:
        print("Inga Garmin-pulszoner för cykling är sparade ännu.")
        return 2
    print(json.dumps({"sport_type": profile.sport_type, "zones": profile.zones}, indent=2))
    return 0


def _plan_service_with_ai() -> TrainingPlanService:
    api_key = resolve_openai_api_key(settings)
    if not api_key:
        raise ValueError("OPENAI_API_KEY saknas; ingen plan har skapats.")
    return TrainingPlanService(
        generator=OpenAIPlanClient(api_key=api_key, model=settings.openai_model)
    )


def run_plan_draft(args: Namespace, *, today: date | None = None) -> int:
    as_of_date = args.end_date or today or date.today()
    try:
        plan = _plan_service_with_ai().generate_draft(
            as_of_date=as_of_date,
            detailed_days=args.days,
            race_id=args.race_id,
        )
    except (ValueError, PaceAIError) as error:
        print(f"Planen kunde inte skapas: {error}")
        return 2
    print(json.dumps(asdict(plan), default=_json_default, indent=2))
    print(f"Granska läsbart: 'pace plan review --id {plan.id}'.")
    print(f"Plan {plan.id} är aktiv. En tidigare aktiv plan ersätts först efter lyckad validering.")
    return 0


def run_plan_list(_args: Namespace) -> int:
    plans = TrainingPlanService().list_plans()
    print(json.dumps([asdict(plan) for plan in plans], default=_json_default, indent=2))
    return 0


def run_plan_show(args: Namespace) -> int:
    try:
        plan = TrainingPlanService().get_plan(plan_id=args.id)
    except ValueError as error:
        print(f"Planen kunde inte visas: {error}")
        return 2
    print(json.dumps(asdict(plan), default=_json_default, indent=2))
    return 0


def run_plan_today(args: Namespace, *, today: date | None = None) -> int:
    on_date = args.date or today or date.today()
    try:
        plan = select_plan_for_today(
            TrainingPlanService().list_plans(),
            on_date=on_date,
            plan_id=args.id,
        )
    except ValueError as error:
        print(f"Dagens plan kunde inte visas: {error}")
        return 2
    print(render_plan_today(plan, on_date=on_date))
    return 0


def run_plan_review(args: Namespace) -> int:
    try:
        plan = TrainingPlanService().get_plan(plan_id=args.id)
    except ValueError as error:
        print(f"Planen kunde inte granskas: {error}")
        return 2
    print(render_plan_review(plan))
    return 0


def run_plan_report(args: Namespace) -> int:
    try:
        plan = TrainingPlanService().get_plan(plan_id=args.id)
        output_path = write_plan_html_report(plan)
    except (OSError, ValueError) as error:
        print(f"HTML-rapporten kunde inte skapas: {error}")
        return 2
    print(f"Privat HTML-rapport sparad: {output_path}")
    print("Öppna filen i din webbläsare. Rapporten ändrar inte planen.")
    return 0


def run_plan_accept(args: Namespace) -> int:
    try:
        plan = TrainingPlanService().accept_plan(plan_id=args.id)
    except ValueError as error:
        print(f"Planutkastet kunde inte accepteras: {error}")
        return 2
    print(f"Plan {plan.id} är accepterad. Tidigare versioner finns kvar lokalt.")
    return 0


def run_plan_feedback(args: Namespace) -> int:
    try:
        TrainingPlanService().add_feedback(
            session_id=args.session_id,
            outcome=args.outcome,
            perceived_exertion=args.rpe,
            reason_code=args.reason,
            note=args.note,
            share_note_with_ai=args.share_note_with_ai,
        )
    except ValueError as error:
        print(f"Passutfallet kunde inte sparas: {error}")
        return 2
    print("Passutfallet är sparat. Ingen plan har ändrats.")
    return 0


def run_plan_workout_evaluate(args: Namespace) -> int:
    try:
        evaluation = WorkoutEvaluationService().evaluate(session_id=args.session_id)
    except ValueError as error:
        print(f"Passet kunde inte utvärderas: {error}")
        return 2
    print(json.dumps(asdict(evaluation), default=_json_default, indent=2))
    return 0


def run_trends_show(args: Namespace, *, today: date | None = None) -> int:
    end_date = args.end_date or today or date.today()
    trends = TrainingResponseTrendService().get_trends(end_date=end_date)
    print(json.dumps(asdict(trends), default=_json_default, indent=2))
    return 0


def run_analysis_show(args: Namespace, *, today: date | None = None) -> int:
    analysis = TransparentTrainingAnalysisService().get_analysis(
        end_date=args.end_date or today or date.today()
    )
    print(json.dumps(asdict(analysis), default=_json_default, indent=2))
    return 0


def run_dashboard(args: Namespace, *, today: date | None = None) -> int:
    end_date = args.end_date or today or date.today()
    try:
        output_path = DashboardService().write_dashboard(end_date=end_date)
    except (OSError, ValueError) as error:
        print(f"Dashboarden kunde inte skapas: {error}")
        return 2
    print(f"Privat dashboard sparad: {output_path}")
    print("Öppna filen i din webbläsare. Dashboarden ändrar inte Pace-data.")
    return 0


def run_home(args: Namespace, *, today: date | None = None) -> int:
    try:
        output_path = HomeService().write_home(
            end_date=args.end_date or today or date.today()
        )
    except (OSError, ValueError) as error:
        print(f"Pace Home kunde inte skapas: {error}")
        return 2
    print(f"Pace Home sparad: {output_path}")
    print("Öppna reports/home.html. Sidan synkar inte Garmin och ändrar ingen plan.")
    return 0


def run_serve(args: Namespace) -> int:
    """Run Pace only on loopback; no cloud hosting or external access exists."""

    import uvicorn

    from pace.web.app import create_app

    try:
        initialize_database(database_url=settings.database_url)
    except Exception:
        print("Pace-databasen kunde inte initieras eller uppgraderas.")
        return 1
    url = f"http://127.0.0.1:{args.port}"
    print(f"Pace Home kör lokalt på {url}")
    print("Stäng med Ctrl+C. Inga data publiceras på nätet.")
    if not args.no_browser:
        Timer(0.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_level="warning")
    return 0


def run_eval_scenarios(_args: Namespace) -> int:
    print(
        json.dumps(
            [
                {
                    "id": item.scenario_id,
                    "description": item.description,
                    "allowed_sports": item.allowed_sports,
                    "allowed_target_kinds": item.allowed_target_kinds,
                }
                for item in load_scenarios()
            ],
            indent=2,
        )
    )
    return 0


def run_eval_coach(args: Namespace) -> int:
    if not args.live:
        print("Live-evalueringen startades inte. Lägg till --live för sex syntetiska AI-anrop.")
        return 2
    api_key = resolve_openai_api_key(settings)
    if not api_key:
        print("OPENAI_API_KEY saknas; ingen live-evaluering kördes.")
        return 2
    report = CoachEvaluationService().evaluate(
        generator=OpenAIPlanClient(api_key=api_key, model=settings.openai_model)
    )
    print(json.dumps(asdict(report), default=_json_default, indent=2))
    return 0 if report.failed == 0 else 1


def run_weekly_review(args: Namespace, *, today: date | None = None) -> int:
    api_key = resolve_openai_api_key(settings)
    if not api_key:
        print("OPENAI_API_KEY saknas; ingen veckoreview skapades.")
        return 2
    try:
        path = WeeklyReviewService(client=WeeklyReviewClient(api_key=api_key, model=settings.openai_model)).create(end_date=args.end_date or today or date.today())
    except (ValueError, PaceAIError) as error:
        print(f"Veckoreviewen kunde inte skapas: {error}")
        return 2
    print(f"Privat veckoreview sparad: {path}")
    print("Öppna filen i din webbläsare. Reviewen ändrar inte planen.")
    return 0


def run_profile_list(args: Namespace, *, today: date | None = None) -> int:
    as_of_date = args.end_date or today or date.today()
    rows = CoachingPrincipleService().list_active(as_of_date=as_of_date)
    print(json.dumps([{"id": item.id, "statement": item.statement, "source_plan_id": item.source_plan_id, "review_due_date": item.review_due_date, "review_due": due} for item, due in rows], default=_json_default, indent=2))
    return 0


def run_profile_accept(args: Namespace, *, today: date | None = None) -> int:
    try:
        item = CoachingPrincipleService().accept_from_plan(plan_id=args.plan_id, principle_index=args.principle_index, as_of_date=args.end_date or today or date.today())
    except ValueError as error:
        print(f"Coachprincipen kunde inte bekräftas: {error}")
        return 2
    print(f"Coachprincip {item.id} är bekräftad till {item.review_due_date}.")
    return 0


def run_profile_archive(args: Namespace) -> int:
    try:
        CoachingPrincipleService().archive(principle_id=args.id)
    except ValueError as error:
        print(f"Coachprincipen kunde inte arkiveras: {error}")
        return 2
    print("Coachprincipen är arkiverad.")
    return 0


def run_plan_revise(args: Namespace, *, today: date | None = None) -> int:
    as_of_date = args.end_date or today or date.today()
    try:
        plan = _plan_service_with_ai().generate_revision(
            plan_id=args.id,
            as_of_date=as_of_date,
            detailed_days=args.days,
        )
    except (ValueError, PaceAIError) as error:
        print(f"Den reviderade planen kunde inte skapas: {error}")
        return 2
    print(json.dumps(asdict(plan), default=_json_default, indent=2))
    print(f"Reviderad plan {plan.id} är aktiv. Den tidigare planen ersattes först efter lyckad validering.")
    return 0


def run_capacity_show(args: Namespace, *, today: date | None = None) -> int:
    """Print factual capacity evidence without inferring a future training load."""

    end_date = args.end_date or today or date.today()
    profile = CapacityService().get_profile(end_date=end_date)
    print(json.dumps(asdict(profile), default=_json_default, indent=2))
    return 0


def run_performance_sync(args: Namespace, *, today: date | None = None) -> int:
    """Import Garmin detail summaries and splits without requesting routes or streams."""

    sync_end_date = getattr(args, "end_date", None) or today or date.today()
    sync_start_date = sync_end_date - timedelta(days=args.days - 1)
    try:
        client = GarminConnectClient.from_saved_tokens(settings.garmin_token_dir)
        result = PerformanceHistoryService(client).sync_details(
            start_date=sync_start_date,
            end_date=sync_end_date,
        )
    except GarminAuthenticationRequiredError as error:
        print(f"Detaljsynken kan inte starta: {error}")
        return 2
    except GarminRateLimitError as error:
        print(f"Detaljsynken stoppades: {error}")
        return 3
    except GarminIntegrationError as error:
        print(f"Detaljsynken misslyckades: {error}")
        return 2
    except Exception:
        print("Detaljsynken misslyckades. Redan sparade detaljer lämnades oförändrade.")
        return 1

    print(
        f"Garmin-detaljsynk klar ({result.start_date} till {result.end_date}): "
        f"{result.candidate_activities} run/ride-kandidater, "
        f"{result.details_fetched} detaljposter hämtade, "
        f"{result.details_inserted} nya och {result.details_updated} uppdaterade."
    )
    if result.status == "partial":
        if result.stop_reason == "rate_limit":
            print("Detaljsynken stoppades av Garmin-gräns. Vänta och kör samma batch igen.")
            return 3
        if result.stop_reason == "authentication":
            print("Garmin-sessionen slutade vara giltig. Logga in igen och kör samma batch.")
            return 2
        print("Detaljsynken är delvis klar. Tidigare detaljer bevarades; kör samma batch igen.")
    return 0


def run_performance_show(args: Namespace, *, today: date | None = None) -> int:
    """Display local performance facts without deriving targets or a plan."""

    end_date = args.end_date or today or date.today()
    history = PerformanceHistoryService().get_history(end_date=end_date)
    print(json.dumps(asdict(history), default=_json_default, indent=2))
    return 0


def run_performance_link_race(args: Namespace) -> int:
    """Persist only an athlete-confirmed race-to-Garmin link."""

    try:
        PerformanceHistoryService().link_race_evidence(
            garmin_activity_id=args.garmin_activity_id,
            race_id=args.race_id,
        )
    except ValueError as error:
        print(f"Loppresultatet kunde inte länkas: {error}")
        return 2
    print("Garmin-aktiviteten är länkad som ett bekräftat loppresultat.")
    return 0


def run_performance_mark_benchmark(args: Namespace) -> int:
    """Store an athlete-confirmed benchmark after deterministic protocol checks."""

    try:
        PerformanceHistoryService().mark_benchmark_evidence(
            garmin_activity_id=args.garmin_activity_id,
            protocol_key=args.protocol,
        )
    except ValueError as error:
        print(f"Benchmark-passet kunde inte markeras: {error}")
        return 2
    print(f"Garmin-aktiviteten är sparad som benchmark: {args.protocol}.")
    return 0


def run_performance_readiness(args: Namespace, *, today: date | None = None) -> int:
    """Display deterministic gates without calculating a target or a training plan."""

    end_date = args.end_date or today or date.today()
    readiness = PerformanceHistoryService().get_readiness(end_date=end_date)
    print(json.dumps(asdict(readiness), default=_json_default, indent=2))
    return 0


def _render_ai_answer(answer: PaceAIAnswer, *, as_of_date: date) -> str:
    """Render a validated AI answer while making unsaved drafts unmistakable."""

    lines = [f"Pace AI ({as_of_date})", answer.answer]
    if answer.observations:
        lines.extend(
            ["", "Observationer:", *[f"- {item}" for item in answer.observations]]
        )
    if answer.uncertainties:
        lines.extend(
            ["", "Osäkerheter:", *[f"- {item}" for item in answer.uncertainties]]
        )
    if answer.knowledge_references:
        lines.extend(
            [
                "",
                "Kunskapsstöd:",
                *[
                    f"- {item} (visa: pace knowledge show --id {item})"
                    for item in answer.knowledge_references
                ],
            ]
        )
    if answer.context_event_draft is not None:
        draft = answer.context_event_draft
        duration = "pågående" if draft.ongoing else str(draft.end_date or draft.start_date)
        lines.extend(
            [
                "",
                "Context-utkast — inte sparat:",
                f"- typ: {draft.event_type}",
                f"- från: {draft.start_date}",
                f"- till: {duration}",
                f"- not: {draft.note}",
                "Bekräfta eller ändra uppgifterna med 'pace note add'; AI:n kan inte spara dem.",
                "Kopiera detta om uppgifterna stämmer:",
                _render_note_add_command(draft),
            ]
        )
    return "\n".join(lines)


def _render_coach_answer(
    answer: CoachDialogueAnswer,
    *,
    plan_id: int,
    as_of_date: date,
) -> str:
    """Make the non-persistent status of a plan adjustment unmistakable."""

    lines = [f"Pace coach ({as_of_date})", answer.answer]
    if answer.observations:
        lines.extend(["", "Observationer:", *[f"- {item}" for item in answer.observations]])
    if answer.uncertainties:
        lines.extend(["", "Osäkerheter:", *[f"- {item}" for item in answer.uncertainties]])
    if answer.knowledge_references:
        lines.extend(
            [
                "",
                "Kunskapsstöd:",
                *[
                    f"- {item} (visa: pace knowledge show --id {item})"
                    for item in answer.knowledge_references
                ],
            ]
        )
    adjustment = answer.adjustment_draft
    if adjustment is not None:
        lines.extend(["", "Planjusteringsutkast — inte sparat:"])
        labels = {"keep_plan": "Behåll plan", "skip": "Hoppa över pass", "replace": "Ersätt pass"}
        lines.extend(
            [
                f"- åtgärd: {labels[adjustment.action]}",
                f"- motivering: {adjustment.rationale}",
            ]
        )
        if adjustment.replaces_session_id is not None:
            lines.append(f"- berört pass-id: {adjustment.replaces_session_id}")
        if adjustment.proposed_session is not None:
            session = adjustment.proposed_session
            lines.append(
                "- föreslaget pass: "
                f"{session.sport_type} · {session.purpose} · "
                f"{_coach_session_scope(session)} · {_coach_target_display(session)}"
            )
        lines.extend(
            [
                "Planen är inte ändrad. Om du vill göra en beständig ny planversion, "
                f"skapa först ett separat revisionsutkast: pace plan revise --id {plan_id} --days 7",
            ]
        )
    return "\n".join(lines)


def _coach_session_scope(session) -> str:
    values = []
    if session.distance_meters is not None:
        values.append(f"{session.distance_meters / 1_000:g} km")
    if session.duration_seconds is not None:
        values.append(f"{session.duration_seconds // 60} min")
    return " · ".join(values) or "ingen omfattning"


def _coach_target_display(session) -> str:
    target = session.target
    values = []
    if session.heart_rate_zone is not None:
        values.append(f"Z{session.heart_rate_zone}")
    if target.kind == "rpe":
        values.append(f"RPE {target.rpe_min}–{target.rpe_max}")
    if target.kind == "pace":
        minutes, seconds = divmod(target.pace_seconds_per_km or 0, 60)
        values.append(f"{minutes}:{seconds:02d} min/km")
    if target.kind == "power":
        values.append(f"{target.power_watts} W")
    return " | ".join(values) or "ingen primär intensitet"


def _render_note_add_command(draft: ContextEventDraft) -> str:
    """Render a shell-safe command for an athlete-confirmed context draft."""

    command = [
        "uv",
        "run",
        "pace",
        "note",
        "add",
        "--type",
        draft.event_type,
        "--date",
        draft.start_date.isoformat(),
    ]
    if draft.ongoing:
        command.append("--ongoing")
    elif draft.end_date is not None and draft.end_date != draft.start_date:
        command.extend(("--end-date", draft.end_date.isoformat()))
    command.append(draft.note)
    return shlex.join(command)


def main(argv: list[str] | None = None) -> int:
    """Run the requested Pace command and return a shell exit status."""

    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)

    if handler is None:
        parser.print_help()
        return 0

    try:
        return handler(args)
    except OperationalError as error:
        if _is_missing_database_schema(error):
            print("Pace-databasen behöver uppdateras. Kör: uv run pace db init")
            return 2
        raise


def _is_missing_database_schema(error: OperationalError) -> bool:
    message = str(error).lower()
    return "no such column" in message or "no such table" in message
