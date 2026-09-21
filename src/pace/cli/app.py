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

from pace.version import __version__
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
from pace.services.heart_rate_zone_service import (
    HeartRateZoneInput,
    HeartRateZoneService,
)
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
        raise ArgumentTypeError("--days must be an integer.") from error

    if days < 1:
        raise ArgumentTypeError("--days must be at least 1.")
    if days > MAX_SYNC_DAYS:
        raise ArgumentTypeError(
            f"--days cannot exceed {MAX_SYNC_DAYS}. "
            "Use --end-date for older seven-day batches."
        )

    return days


def plan_days(value: str) -> int:
    try:
        days = int(value)
    except ValueError as error:
        raise ArgumentTypeError("--days must be 7 or 14.") from error
    if days not in {7, 14}:
        raise ArgumentTypeError("--days must be 7 or 14.")
    return days


def feedback_rpe(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ArgumentTypeError("--rpe must be an integer from 1 to 10.") from error
    if not 1 <= parsed <= 10:
        raise ArgumentTypeError("--rpe must be between 1 and 10.")
    return parsed


def local_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise ArgumentTypeError(
            "--port must be an integer between 1024 and 65535."
        ) from error
    if not 1024 <= port <= 65_535:
        raise ArgumentTypeError("--port must be between 1024 and 65535.")
    return port


def iso_date(value: str) -> date:
    """Parse an ISO calendar date supplied to the CLI."""

    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ArgumentTypeError("Date must use the YYYY-MM-DD format.") from error


def positive_distance_km(value: str) -> float:
    """Parse a positive race distance in the athlete-facing unit."""

    try:
        distance_km = float(value)
    except ValueError as error:
        raise ArgumentTypeError("Distance must be a number in kilometres.") from error
    if distance_km <= 0:
        raise ArgumentTypeError("Distance must be greater than zero.")
    return distance_km


def duration_seconds(value: str) -> int:
    """Parse an optional race goal time in H:MM:SS format."""

    parts = value.split(":")
    if len(parts) != 3:
        raise ArgumentTypeError("Desired time must use the H:MM:SS format.")
    try:
        hours, minutes, seconds = (int(part) for part in parts)
    except ValueError as error:
        raise ArgumentTypeError("Desired time must use the H:MM:SS format.") from error
    if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
        raise ArgumentTypeError("Desired time must use the H:MM:SS format.")
    total_seconds = hours * 3600 + minutes * 60 + seconds
    if total_seconds <= 0:
        raise ArgumentTypeError("Desired time must be greater than zero.")
    return total_seconds


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        prog="pace",
        description="A private, local-first endurance coaching system.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"pace {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    db_parser = subparsers.add_parser(
        "db",
        help="initialize and upgrade the local database",
    )
    db_subparsers = db_parser.add_subparsers(dest="db_command")
    db_init_parser = db_subparsers.add_parser(
        "init",
        help="applicera Pace-databasens Alembic-migreringar",
    )
    db_init_parser.set_defaults(handler=run_db_init)

    garmin_parser = subparsers.add_parser(
        "garmin",
        help="manage Garmin login",
    )
    garmin_subparsers = garmin_parser.add_subparsers(dest="garmin_command")
    login_parser = garmin_subparsers.add_parser(
        "login",
        help="log in and save a local Garmin session",
    )
    login_parser.add_argument(
        "--email",
        help="Garmin email. Omit it to enter the address in a private prompt.",
    )
    login_parser.set_defaults(handler=run_garmin_login)

    sync_parser = subparsers.add_parser(
        "sync",
        help="fetch Garmin activities and recovery data into the local database",
    )
    sync_parser.add_argument(
        "--days",
        type=positive_days,
        default=7,
        help="calendar days including the batch end date (default: 7)",
    )
    sync_parser.add_argument(
        "--end-date",
        type=iso_date,
        help=(
            "last date in the batch, YYYY-MM-DD "
            "(default: today; use it for older history)"
        ),
    )
    sync_parser.set_defaults(handler=run_sync)

    note_parser = subparsers.add_parser(
        "note",
        help="save and show local athlete context",
    )
    note_subparsers = note_parser.add_subparsers(dest="note_command")
    note_add_parser = note_subparsers.add_parser(
        "add",
        help="save a structured context note",
    )
    note_add_parser.add_argument(
        "--type",
        dest="event_type",
        choices=sorted(SUPPORTED_CONTEXT_EVENT_TYPES),
        required=True,
        help="type of context that Garmin cannot observe",
    )
    note_add_parser.add_argument(
        "--date",
        dest="start_date",
        type=iso_date,
        required=True,
        help="first date of the event, YYYY-MM-DD",
    )
    note_add_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="last date of a time-limited event, YYYY-MM-DD",
    )
    note_add_parser.add_argument(
        "--ongoing",
        action="store_true",
        help="mark the event as ongoing instead of time-limited",
    )
    note_add_parser.add_argument(
        "note",
        help="short private description; quote it if it contains spaces",
    )
    note_add_parser.set_defaults(handler=run_note_add)

    note_list_parser = note_subparsers.add_parser(
        "list",
        help="show saved context notes",
    )
    note_list_parser.add_argument(
        "--from",
        dest="start_date",
        type=iso_date,
        help="first date in an overlapping filter, YYYY-MM-DD",
    )
    note_list_parser.add_argument(
        "--to",
        dest="end_date",
        type=iso_date,
        help="last date in an overlapping filter, YYYY-MM-DD",
    )
    note_list_parser.set_defaults(handler=run_note_list)

    metrics_parser = subparsers.add_parser(
        "metrics",
        help="calculate deterministic training and recovery metrics",
    )
    metrics_subparsers = metrics_parser.add_subparsers(dest="metrics_command")
    metrics_summary_parser = metrics_subparsers.add_parser(
        "summary",
        help="show training and recovery facts",
    )
    metrics_summary_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="last date in the analysis, YYYY-MM-DD (default: today)",
    )
    metrics_summary_parser.set_defaults(handler=run_metrics_summary)

    state_parser = subparsers.add_parser(
        "state",
        help="show a local snapshot of facts, context, and data quality",
    )
    state_subparsers = state_parser.add_subparsers(dest="state_command")
    state_show_parser = state_subparsers.add_parser(
        "show",
        help="show athlete state without coaching interpretation",
    )
    state_show_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="last date in the state window, YYYY-MM-DD (default: today)",
    )
    state_show_parser.set_defaults(handler=run_state_show)

    rules_parser = subparsers.add_parser(
        "rules",
        help="evaluate transparent Pace rules without coaching advice",
    )
    rules_subparsers = rules_parser.add_subparsers(dest="rules_command")
    rules_evaluate_parser = rules_subparsers.add_parser(
        "evaluate",
        help="show structured rule results",
    )
    rules_evaluate_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="last date in the rule evaluation, YYYY-MM-DD (default: today)",
    )
    rules_evaluate_parser.set_defaults(handler=run_rules_evaluate)

    explain_parser = subparsers.add_parser(
        "explain",
        help="explain Pace rules with local deterministic templates",
    )
    explain_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="last date in the explanation, YYYY-MM-DD (default: today)",
    )
    explain_parser.set_defaults(handler=run_explain)

    ask_parser = subparsers.add_parser(
        "ask",
        help="ask the AI assistant about selected local Pace facts",
    )
    ask_parser.add_argument(
        "question",
        help="an optional question; each question is handled independently",
    )
    ask_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="last date in the fact set, YYYY-MM-DD (default: today)",
    )
    ask_parser.set_defaults(handler=run_ask)

    knowledge_parser = subparsers.add_parser(
        "knowledge",
        help="show Pace's local curated knowledge base without a network call",
    )
    knowledge_subparsers = knowledge_parser.add_subparsers(dest="knowledge_command")
    knowledge_list_parser = knowledge_subparsers.add_parser(
        "list", help="list available knowledge briefs"
    )
    knowledge_list_parser.set_defaults(handler=run_knowledge_list)
    knowledge_show_parser = knowledge_subparsers.add_parser(
        "show", help="show a brief, its limitations, and sources"
    )
    knowledge_show_parser.add_argument("--id", dest="brief_id", required=True)
    knowledge_show_parser.set_defaults(handler=run_knowledge_show)

    coach_parser = subparsers.add_parser(
        "coach",
        help="discuss today's active plan with the AI coach without changing it",
    )
    coach_subparsers = coach_parser.add_subparsers(dest="coach_command")
    coach_ask_parser = coach_subparsers.add_parser(
        "ask", help="ask a quick question about today's active plan"
    )
    coach_ask_parser.add_argument("question")
    coach_ask_parser.add_argument("--plan-id", type=int, required=True)
    coach_ask_parser.add_argument("--end-date", type=iso_date)
    coach_ask_parser.set_defaults(handler=run_coach_ask)
    coach_chat_parser = coach_subparsers.add_parser(
        "chat", help="open a short-lived coach dialogue for today's active plan"
    )
    coach_chat_parser.add_argument("--plan-id", type=int, required=True)
    coach_chat_parser.add_argument("--end-date", type=iso_date)
    coach_chat_parser.set_defaults(handler=run_coach_chat)

    race_parser = subparsers.add_parser(
        "race",
        help="manage upcoming races for future planning",
    )
    race_subparsers = race_parser.add_subparsers(dest="race_command")
    race_add_parser = race_subparsers.add_parser(
        "add",
        help="save an upcoming A-, B-, or C-priority race",
    )
    race_add_parser.add_argument("name", help="race name")
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
        help="A = primary goal, B = secondary goal, C = hard training session",
    )
    race_add_parser.add_argument(
        "--desired-time",
        type=duration_seconds,
        help="desired time H:MM:SS; a goal, not capacity evidence",
    )
    race_add_parser.add_argument(
        "--taper",
        choices=sorted(SUPPORTED_TAPER_CHOICES),
        help="override the A/B/C default for this race",
    )
    race_add_parser.set_defaults(handler=run_race_add)

    race_list_parser = race_subparsers.add_parser(
        "list",
        help="show upcoming races and their taper policy",
    )
    race_list_parser.add_argument(
        "--as-of-date",
        type=iso_date,
        help="show races from this date, YYYY-MM-DD (default: today)",
    )
    race_list_parser.add_argument(
        "--include-past",
        action="store_true",
        help="include past races, for example to link a Garmin result",
    )
    race_list_parser.add_argument(
        "--include-cancelled",
        action="store_true",
        help="include cancelled future races in the list",
    )
    race_list_parser.set_defaults(handler=run_race_list)

    race_update_parser = race_subparsers.add_parser(
        "update",
        help="correct an unused race or change its priority/taper",
    )
    race_update_parser.add_argument("--id", type=int, required=True)
    race_update_parser.add_argument("--name")
    race_update_parser.add_argument("--date", type=iso_date)
    race_update_parser.add_argument(
        "--sport", choices=sorted(SUPPORTED_RACE_SPORT_TYPES)
    )
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
        "remove", help="permanently remove an unused future race"
    )
    race_remove_parser.add_argument("--id", type=int, required=True)
    race_remove_parser.set_defaults(handler=run_race_remove)
    race_cancel_parser = race_subparsers.add_parser(
        "cancel", help="cancel a future race without deleting history"
    )
    race_cancel_parser.add_argument("--id", type=int, required=True)
    race_cancel_parser.set_defaults(handler=run_race_cancel)

    plan_parser = subparsers.add_parser(
        "plan",
        help="create, review, and follow local Pace plans",
    )
    plan_subparsers = plan_parser.add_subparsers(dest="plan_command")
    plan_readiness_parser = plan_subparsers.add_parser(
        "readiness",
        help="check Garmin history, active health blockers, and races",
    )
    plan_readiness_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="planning date YYYY-MM-DD (default: today)",
    )
    plan_readiness_parser.set_defaults(handler=run_plan_readiness)

    plan_checkpoint_parser = plan_subparsers.add_parser(
        "checkpoint",
        help="show when the next explicit plan revision is due and which races are approaching",
    )
    plan_checkpoint_parser.add_argument("--end-date", type=iso_date)
    plan_checkpoint_parser.set_defaults(handler=run_plan_checkpoint)

    plan_draft_parser = plan_subparsers.add_parser(
        "draft",
        help="create and activate a validated AI-generated plan",
    )
    plan_draft_parser.add_argument(
        "--race-id",
        type=int,
        help="optional active race defining the block; omit for a general goal",
    )
    plan_draft_parser.add_argument(
        "--days",
        type=plan_days,
        default=14,
        help="number of detailed days, 7 or 14 (default: 14)",
    )
    plan_draft_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="planning date YYYY-MM-DD (default: today)",
    )
    plan_draft_parser.set_defaults(handler=run_plan_draft)

    plan_list_parser = plan_subparsers.add_parser(
        "list",
        help="show local plans and previous versions",
    )
    plan_list_parser.set_defaults(handler=run_plan_list)

    plan_show_parser = plan_subparsers.add_parser(
        "show",
        help="show a local plan version",
    )
    plan_show_parser.add_argument("--id", type=int, required=True)
    plan_show_parser.set_defaults(handler=run_plan_show)

    plan_today_parser = plan_subparsers.add_parser(
        "today",
        help="show today's or the next session in readable form",
    )
    plan_today_parser.add_argument(
        "--id",
        type=int,
        help="optional plan id; required to preview a draft",
    )
    plan_today_parser.add_argument(
        "--date",
        type=iso_date,
        help="date YYYY-MM-DD (default: today)",
    )
    plan_today_parser.set_defaults(handler=run_plan_today)

    plan_review_parser = plan_subparsers.add_parser(
        "review",
        help="show a plan, coach assessment, and outcomes in readable form",
    )
    plan_review_parser.add_argument("--id", type=int, required=True)
    plan_review_parser.set_defaults(handler=run_plan_review)

    plan_report_parser = plan_subparsers.add_parser(
        "report",
        help="create a private HTML report for a local plan",
    )
    plan_report_parser.add_argument("--id", type=int, required=True)
    plan_report_parser.set_defaults(handler=run_plan_report)

    plan_accept_parser = plan_subparsers.add_parser(
        "accept",
        help="accept an older legacy draft without deleting plan versions",
    )
    plan_accept_parser.add_argument("--id", type=int, required=True)
    plan_accept_parser.set_defaults(handler=run_plan_accept)

    plan_exception_parser = plan_subparsers.add_parser(
        "approve-volume-exception",
        help="explicitly approve and activate a pending race-volume exception",
    )
    plan_exception_parser.add_argument("--id", type=int, required=True)
    plan_exception_parser.set_defaults(handler=run_plan_approve_volume_exception)

    plan_feedback_parser = plan_subparsers.add_parser(
        "feedback",
        help="save a structured outcome for an active planned session",
    )
    plan_feedback_parser.add_argument("--session-id", type=int, required=True)
    plan_feedback_parser.add_argument(
        "--outcome", choices=sorted(SUPPORTED_FEEDBACK_OUTCOMES), required=True
    )
    plan_feedback_parser.add_argument(
        "--rpe",
        type=feedback_rpe,
        help="optional perceived exertion 1–10; used only for completed sessions",
    )
    plan_feedback_parser.add_argument(
        "--reason",
        choices=sorted(SUPPORTED_FEEDBACK_REASON_CODES),
        help="optional structured reason for a limited or skipped session",
    )
    plan_feedback_parser.add_argument("--note", help="valfri lokal notering")
    plan_feedback_parser.add_argument(
        "--share-note-with-ai",
        action="store_true",
        help="allow this specific note to be sent in a future revision request",
    )
    plan_feedback_parser.set_defaults(handler=run_plan_feedback)

    plan_workout_parser = plan_subparsers.add_parser(
        "workout",
        help="evaluate a planned session against explicit feedback and same-day Garmin data",
    )
    plan_workout_subparsers = plan_workout_parser.add_subparsers(
        dest="plan_workout_command"
    )
    plan_workout_evaluate_parser = plan_workout_subparsers.add_parser(
        "evaluate",
        help="evaluate without changing the plan or recording completion automatically",
    )
    plan_workout_evaluate_parser.add_argument("--session-id", type=int, required=True)
    plan_workout_evaluate_parser.set_defaults(handler=run_plan_workout_evaluate)

    plan_revise_parser = plan_subparsers.add_parser(
        "revise",
        help="create and activate a short revised plan after validation",
    )
    plan_revise_parser.add_argument("--id", type=int, required=True)
    plan_revise_parser.add_argument("--days", type=plan_days, default=14)
    plan_revise_parser.add_argument("--end-date", type=iso_date)
    plan_revise_parser.set_defaults(handler=run_plan_revise)

    trends_parser = subparsers.add_parser(
        "trends",
        help="show local trends from explicitly reported session feedback",
    )
    trends_subparsers = trends_parser.add_subparsers(dest="trends_command")
    trends_show_parser = trends_subparsers.add_parser(
        "show", help="show two 28-day windows without changing any plan"
    )
    trends_show_parser.add_argument(
        "--end-date", type=iso_date, help="end date YYYY-MM-DD (default: today)"
    )
    trends_show_parser.set_defaults(handler=run_trends_show)

    analysis_parser = subparsers.add_parser(
        "analysis",
        help="show transparent training facts without a hidden load score",
    )
    analysis_subparsers = analysis_parser.add_subparsers(dest="analysis_command")
    analysis_show_parser = analysis_subparsers.add_parser(
        "show",
        help="show a local 28-day window for training, feedback, and data coverage",
    )
    analysis_show_parser.add_argument(
        "--end-date", type=iso_date, help="end date YYYY-MM-DD (default: today)"
    )
    analysis_show_parser.set_defaults(handler=run_analysis_show)

    dashboard_parser = subparsers.add_parser(
        "dashboard", help="create a dense local HTML dashboard"
    )
    dashboard_parser.add_argument(
        "--end-date", type=iso_date, help="date YYYY-MM-DD (default: today)"
    )
    dashboard_parser.set_defaults(handler=run_dashboard)

    home_parser = subparsers.add_parser(
        "home", help="create a central local HTML home page for Pace"
    )
    home_parser.add_argument(
        "--end-date", type=iso_date, help="date YYYY-MM-DD (default: today)"
    )
    home_parser.set_defaults(handler=run_home)

    serve_parser = subparsers.add_parser(
        "serve",
        help="start Pace Home as a private local browser app",
    )
    serve_parser.add_argument(
        "--port",
        type=local_port,
        default=8765,
        help="local port on 127.0.0.1 (default: 8765)",
    )
    serve_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="do not open the browser automatically",
    )
    serve_parser.set_defaults(handler=run_serve)

    eval_parser = subparsers.add_parser(
        "eval", help="review Pace's coaching contract with synthetic scenarios"
    )
    eval_subparsers = eval_parser.add_subparsers(dest="eval_command")
    eval_scenarios_parser = eval_subparsers.add_parser(
        "scenarios", help="list the local offline coach-evaluation catalog"
    )
    eval_scenarios_parser.set_defaults(handler=run_eval_scenarios)
    eval_coach_parser = eval_subparsers.add_parser(
        "coach", help="run an explicit live AI test against synthetic facts"
    )
    eval_coach_parser.add_argument(
        "--live",
        action="store_true",
        help="confirm six OpenAI calls; no real athlete data is used",
    )
    eval_coach_parser.set_defaults(handler=run_eval_coach)

    review_parser = subparsers.add_parser(
        "review", help="create an explicit AI weekly review as local HTML"
    )
    review_subparsers = review_parser.add_subparsers(dest="review_command")
    weekly_review_parser = review_subparsers.add_parser(
        "weekly", help="analyse the latest week without changing the plan"
    )
    weekly_review_parser.add_argument("--end-date", type=iso_date)
    weekly_review_parser.set_defaults(handler=run_weekly_review)

    profile_parser = subparsers.add_parser(
        "profile", help="manage confirmed personal coaching principles"
    )
    profile_subparsers = profile_parser.add_subparsers(dest="profile_command")
    profile_list_parser = profile_subparsers.add_parser(
        "list", help="show active and review-due principles"
    )
    profile_list_parser.add_argument("--end-date", type=iso_date)
    profile_list_parser.set_defaults(handler=run_profile_list)
    profile_accept_parser = profile_subparsers.add_parser(
        "accept", help="confirm a coaching principle from a plan draft"
    )
    profile_accept_parser.add_argument("--plan-id", type=int, required=True)
    profile_accept_parser.add_argument("--principle-index", type=int, required=True)
    profile_accept_parser.add_argument("--end-date", type=iso_date)
    profile_accept_parser.set_defaults(handler=run_profile_accept)
    profile_archive_parser = profile_subparsers.add_parser(
        "archive", help="archive a confirmed coaching principle"
    )
    profile_archive_parser.add_argument("--id", type=int, required=True)
    profile_archive_parser.set_defaults(handler=run_profile_archive)

    preferences_parser = subparsers.add_parser(
        "preferences",
        help="manage availability and sport role for future plan drafts",
    )
    preferences_subparsers = preferences_parser.add_subparsers(
        dest="preferences_command"
    )
    preferences_set_parser = preferences_subparsers.add_parser(
        "set", help="save available days and preferred sport role"
    )
    preferences_set_parser.add_argument(
        "--sport-role", choices=sorted(SUPPORTED_SPORT_ROLES), required=True
    )
    preferences_set_parser.add_argument(
        "--ambition",
        choices=sorted(SUPPORTED_COACHING_AMBITIONS),
        help=(
            "cautious = larger margins, balanced = default, "
            "ambitious = more assertive drafts when the facts support them"
        ),
    )
    preferences_set_parser.add_argument(
        "--day",
        action="append",
        required=True,
        help="availability such as mon:60 or mon:any; repeat for multiple days",
    )
    preferences_set_parser.add_argument(
        "--base-run-km",
        type=float,
        help="hard base-phase running ceiling in kilometres per calendar week",
    )
    preferences_set_parser.add_argument(
        "--base-ride-hours",
        type=float,
        help="hard base-phase cycling ceiling in hours per calendar week",
    )
    preferences_set_parser.add_argument(
        "--base-total-hours",
        type=float,
        help="hard combined base-phase ceiling in hours per calendar week",
    )
    preferences_set_parser.set_defaults(handler=run_preferences_set)
    preferences_show_parser = preferences_subparsers.add_parser(
        "show", help="show saved availability and sport role"
    )
    preferences_show_parser.set_defaults(handler=run_preferences_show)
    preferences_ambition_parser = preferences_subparsers.add_parser(
        "ambition", help="change coaching ambition without rewriting available days"
    )
    preferences_ambition_parser.add_argument(
        "--ambition", choices=sorted(SUPPORTED_COACHING_AMBITIONS), required=True
    )
    preferences_ambition_parser.set_defaults(handler=run_preferences_ambition)

    zones_parser = subparsers.add_parser(
        "zones",
        help="save and show manually confirmed Garmin heart-rate zones for cycling",
    )
    zones_subparsers = zones_parser.add_subparsers(dest="zones_command")
    zones_set_parser = zones_subparsers.add_parser(
        "set", help="save five Garmin heart-rate zones for cycling"
    )
    zones_set_parser.add_argument("--sport", choices=["ride"], required=True)
    zones_set_parser.add_argument(
        "--zone",
        action="append",
        required=True,
        help="Garmin zone such as 1:100-120; provide exactly five values for Z1–Z5",
    )
    zones_set_parser.set_defaults(handler=run_zones_set)
    zones_show_parser = zones_subparsers.add_parser(
        "show", help="show saved Garmin heart-rate zones"
    )
    zones_show_parser.add_argument("--sport", choices=["ride"], default="ride")
    zones_show_parser.set_defaults(handler=run_zones_show)

    capacity_parser = subparsers.add_parser(
        "capacity",
        help="show deterministic facts about observed training capacity",
    )
    capacity_subparsers = capacity_parser.add_subparsers(dest="capacity_command")
    capacity_show_parser = capacity_subparsers.add_parser(
        "show",
        help="show volume, continuity, sport balance, and data quality",
    )
    capacity_show_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="analysis date YYYY-MM-DD (default: today)",
    )
    capacity_show_parser.set_defaults(handler=run_capacity_show)

    performance_parser = subparsers.add_parser(
        "performance",
        help="manage bounded Garmin details and verifiable race results",
    )
    performance_subparsers = performance_parser.add_subparsers(
        dest="performance_command"
    )
    performance_sync_parser = performance_subparsers.add_parser(
        "sync",
        help="fetch local run/ride details and splits for a seven-day batch",
    )
    performance_sync_parser.add_argument(
        "--days",
        type=positive_days,
        default=7,
        help="calendar days including the batch end date (default: 7)",
    )
    performance_sync_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="last date in the batch, YYYY-MM-DD (default: today)",
    )
    performance_sync_parser.set_defaults(handler=run_performance_sync)

    performance_show_parser = performance_subparsers.add_parser(
        "show",
        help="show twelve weeks of detail coverage and explicitly linked race results",
    )
    performance_show_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="last date in the analysis, YYYY-MM-DD (default: today)",
    )
    performance_show_parser.set_defaults(handler=run_performance_show)

    performance_link_race_parser = performance_subparsers.add_parser(
        "link-race",
        help="link a confirmed race to a detailed Garmin activity",
    )
    performance_link_race_parser.add_argument(
        "--garmin-activity-id",
        required=True,
        help="Garmin id from 'pace performance show'",
    )
    performance_link_race_parser.add_argument(
        "--race-id",
        type=int,
        required=True,
        help="local race id from 'pace race list --include-past'",
    )
    performance_link_race_parser.set_defaults(handler=run_performance_link_race)

    performance_benchmark_parser = performance_subparsers.add_parser(
        "mark-benchmark",
        help="mark a completed Pace-defined benchmark session",
    )
    performance_benchmark_parser.add_argument(
        "--garmin-activity-id",
        required=True,
        help="Garmin id from 'pace performance show'",
    )
    performance_benchmark_parser.add_argument(
        "--protocol",
        choices=sorted(SUPPORTED_BENCHMARK_PROTOCOLS),
        required=True,
        help="the Pace protocol the activity must satisfy",
    )
    performance_benchmark_parser.set_defaults(handler=run_performance_mark_benchmark)

    performance_readiness_parser = performance_subparsers.add_parser(
        "readiness",
        help="check whether evidence and current sport history support intensity targets",
    )
    performance_readiness_parser.add_argument(
        "--end-date",
        type=iso_date,
        help="analysis date YYYY-MM-DD (default: today)",
    )
    performance_readiness_parser.set_defaults(handler=run_performance_readiness)

    return parser


def run_db_init(_args: Namespace) -> int:
    """Apply every reviewed Alembic migration to Pace's local database."""

    try:
        initialize_database(database_url=settings.database_url)
    except Exception:
        print("The database could not be initialized or upgraded.")
        return 1

    print("The Pace database is initialized and upgraded to the latest schema.")
    return 0


def run_garmin_login(args: Namespace) -> int:
    """Prompt for credentials once and let the Garmin library save a session."""

    email = args.email or input("Garmin email: ").strip()
    password = getpass("Garmin password: ")

    if not email or not password:
        print("Login cancelled: email and password are required.")
        return 2

    try:
        GarminConnectClient.login_with_credentials(
            email=email,
            password=password,
            token_dir=settings.garmin_token_dir,
            prompt_mfa=lambda: getpass("Garmin MFA code: ").strip(),
        )
    except GarminRateLimitError as error:
        print(f"Garmin login stopped: {error}")
        return 3
    except GarminIntegrationError as error:
        print(f"Garmin login failed: {error}")
        return 2

    print(
        "Garmin is connected. A local session has been saved in "
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
        print(f"The sync could not start: {error}")
        return 2
    except GarminRateLimitError as error:
        print(f"The sync stopped: {error}")
        return 3
    except GarminIntegrationError as error:
        print(f"The sync failed: {error}")
        return 2
    except Exception:
        print("The sync failed. The database was left unchanged for this sync.")
        return 1

    print(
        f"Garmin sync complete ({result.start_date} to {result.end_date}): "
        f"{result.activities_fetched} fetched, "
        f"{result.activities_inserted} new, "
        f"{result.activities_updated} updated activities; "
        f"{result.daily_metrics_fetched} recovery days, "
        f"{result.daily_metrics_inserted} new and "
        f"{result.daily_metrics_updated} updated recovery records."
    )

    if result.status == "partial":
        if result.recovery_stop_reason == "rate_limit":
            print(
                "Recovery data was partially fetched because Garmin rate-limited "
                "the requests. Available values were saved; wait and run "
                "the same batch again later."
            )
            return 3
        if result.recovery_stop_reason == "authentication":
            print(
                "Recovery data was partially fetched because the Garmin session "
                "became invalid. Available values were saved; run "
                "'pace garmin login' and then run the same batch again."
            )
            return 2

        print(
            "Recovery data was partially fetched. Activities and available "
            "recovery values were saved; run the same batch again later for the rest."
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
        print(f"The context note could not be saved: {error}")
        return 2

    duration = "ongoing" if event.end_date is None else str(event.end_date)
    print(
        f"Context note saved: {event.event_type}, from {event.start_date} to {duration}."
    )
    return 0


def run_note_list(args: Namespace) -> int:
    """Print local context events as structured data requested by the athlete."""

    try:
        events = ContextService().list_events(
            start_date=args.start_date,
            end_date=args.end_date,
        )
    except ValueError as error:
        print(f"Context notes could not be fetched: {error}")
        return 2

    print(
        json.dumps([asdict(event) for event in events], default=_json_default, indent=2)
    )
    return 0


def _json_default(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Cannot serialize {type(value).__name__} to JSON.")


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
        print("The question cannot be empty.")
        return 2
    try:
        openai_api_key = resolve_openai_api_key(settings)
    except ValueError as error:
        print(f"The AI assistant is not configured: {error}")
        return 2
    if not openai_api_key:
        print(
            "The AI assistant is not configured. Set OPENAI_API_KEY locally and "
            "run the same command again. No Pace data was sent."
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
        print(f"The knowledge library could not be read: {error}")
        return 2
    print("Pace local knowledge briefs")
    for brief in library.briefs:
        print(f"- {brief.id}: {brief.title} ({', '.join(brief.topic_tags)})")
    print("Showing local reviewed summaries. Nothing was fetched from the internet.")
    return 0


def run_knowledge_show(args: Namespace) -> int:
    """Render one local brief with its claims, limits, and source links."""

    try:
        library = load_knowledge_library()
    except KnowledgeLibraryError as error:
        print(f"The knowledge library could not be read: {error}")
        return 2
    brief = brief_by_id(library, brief_id=args.brief_id)
    if brief is None:
        print(
            f"No knowledge brief has id '{args.brief_id}'. Run 'pace knowledge list'."
        )
        return 2
    lines = [brief.title, f"ID: {brief.id}", "", "Supported claims:"]
    lines.extend(f"- {claim}" for claim in brief.supported_claims)
    lines.extend(["", "Limitations:"])
    lines.extend(f"- {limitation}" for limitation in brief.limitations)
    lines.extend(
        ["", "When Pace may use it:", f"- {brief.applicability}", "", "Sources:"]
    )
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
        raise ValueError("OPENAI_API_KEY is missing; coach dialogue cannot start.")
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
        print(f"The coach dialogue could not be completed: {error}")
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
        print(f"The coach dialogue could not start: {error}")
        return 2
    print(
        f"Pace coach ({end_date}) for active plan {plan.id}. "
        "Enter 'exit' to close. The dialogue is not saved."
    )
    conversation: tuple[dict[str, str], ...] = ()
    while True:
        try:
            question = input("You: ").strip()
        except EOFError, KeyboardInterrupt:
            print("\nCoach dialogue closed. Nothing was saved.")
            return 0
        if question.casefold() in {"avsluta", "exit", "quit"}:
            print("Coach dialogue closed. Nothing was saved.")
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
            print(f"The coach dialogue could not answer: {error}")
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
        print(f"The race could not be saved: {error}")
        return 2

    print(
        f"Race saved: {race.name} ({race.race_date}), priority {race.priority}, "
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
        print(f"The race could not be updated: {error}")
        return 2

    print(
        f"Race updated: {race.name} ({race.race_date}), priority "
        f"{race.priority}, taper {resolved_taper(race)}."
    )
    return 0


def run_race_remove(args: Namespace, *, today: date | None = None) -> int:
    try:
        RaceService().remove_race(race_id=args.id, as_of_date=today or date.today())
    except ValueError as error:
        print(f"The race could not be removed: {error}")
        return 2
    print("The race has been removed. No plans or Garmin results were affected.")
    return 0


def run_race_cancel(args: Namespace, *, today: date | None = None) -> int:
    try:
        race = RaceService().cancel_race(
            race_id=args.id, as_of_date=today or date.today()
        )
    except ValueError as error:
        print(f"The race could not be cancelled: {error}")
        return 2
    print(f"The race is cancelled: {race.name}. It will not be used in new planning.")
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
                base_running_distance_ceiling_km=args.base_run_km,
                base_cycling_duration_ceiling_hours=args.base_ride_hours,
                base_total_duration_ceiling_hours=args.base_total_hours,
            )
        )
    except ValueError as error:
        print(f"The planning preferences could not be saved: {error}")
        return 2
    print(
        f"Planning preferences saved: {preference.sport_role}, "
        f"ambition {preference.coaching_ambition}, "
        f"{len(preference.available_days)} available days."
    )
    return 0


def run_preferences_show(_args: Namespace) -> int:
    preference = TrainingPreferenceService().get_preference()
    if preference is None:
        print("No planning preferences have been saved yet.")
        return 2
    print(
        json.dumps(
            {
                "sport_role": preference.sport_role,
                "coaching_ambition": preference.coaching_ambition,
                "base_running_distance_ceiling_km": getattr(
                    preference, "base_running_distance_ceiling_km", None
                ),
                "base_cycling_duration_ceiling_hours": getattr(
                    preference, "base_cycling_duration_ceiling_hours", None
                ),
                "base_total_duration_ceiling_hours": getattr(
                    preference, "base_total_duration_ceiling_hours", None
                ),
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
        print(f"The coaching ambition could not be saved: {error}")
        return 2
    print(f"Coaching ambition saved: {preference.coaching_ambition}.")
    return 0


def run_zones_set(args: Namespace) -> int:
    try:
        profile = HeartRateZoneService().set_profile(
            HeartRateZoneInput(sport_type=args.sport, zones=tuple(args.zone))
        )
    except ValueError as error:
        print(f"The Garmin heart-rate zones could not be saved: {error}")
        return 2
    print("Garmin heart-rate zones for cycling have been saved locally.")
    print(
        json.dumps({"sport_type": profile.sport_type, "zones": profile.zones}, indent=2)
    )
    return 0


def run_zones_show(args: Namespace) -> int:
    profile = HeartRateZoneService().get_profile(sport_type=args.sport)
    if profile is None:
        print("No Garmin heart-rate zones for cycling have been saved yet.")
        return 2
    print(
        json.dumps({"sport_type": profile.sport_type, "zones": profile.zones}, indent=2)
    )
    return 0


def _plan_service_with_ai() -> TrainingPlanService:
    api_key = resolve_openai_api_key(settings)
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing; no plan was created.")
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
        print(f"The plan could not be created: {error}")
        return 2
    print(json.dumps(asdict(plan), default=_json_default, indent=2))
    print(f"Review it in readable form: 'pace plan review --id {plan.id}'.")
    if plan.status == "volume_exception_pending":
        print(
            f"Plan {plan.id} exceeds a base-volume boundary and is not active. "
            f"Review it, then approve the race-volume exception with "
            f"'pace plan approve-volume-exception --id {plan.id}'."
        )
    else:
        print(
            f"Plan {plan.id} is active. A previous active plan is replaced only after "
            "successful validation."
        )
    return 0


def run_plan_approve_volume_exception(args: Namespace) -> int:
    try:
        plan = TrainingPlanService().approve_volume_exception(plan_id=args.id)
    except ValueError as error:
        print(f"The race-volume exception could not be approved: {error}")
        return 2
    print(f"Race-volume exception approved. Plan {plan.id} is now active.")
    return 0


def run_plan_list(_args: Namespace) -> int:
    plans = TrainingPlanService().list_plans()
    print(json.dumps([asdict(plan) for plan in plans], default=_json_default, indent=2))
    return 0


def run_plan_show(args: Namespace) -> int:
    try:
        plan = TrainingPlanService().get_plan(plan_id=args.id)
    except ValueError as error:
        print(f"The plan could not be shown: {error}")
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
        print(f"Today's plan could not be shown: {error}")
        return 2
    print(render_plan_today(plan, on_date=on_date))
    return 0


def run_plan_review(args: Namespace) -> int:
    try:
        plan = TrainingPlanService().get_plan(plan_id=args.id)
    except ValueError as error:
        print(f"The plan could not be reviewed: {error}")
        return 2
    print(render_plan_review(plan))
    return 0


def run_plan_report(args: Namespace) -> int:
    try:
        plan = TrainingPlanService().get_plan(plan_id=args.id)
        output_path = write_plan_html_report(plan)
    except (OSError, ValueError) as error:
        print(f"The HTML report could not be created: {error}")
        return 2
    print(f"Private HTML report saved: {output_path}")
    print("Open the file in your browser. The report does not change the plan.")
    return 0


def run_plan_accept(args: Namespace) -> int:
    try:
        plan = TrainingPlanService().accept_plan(plan_id=args.id)
    except ValueError as error:
        print(f"The plan draft could not be accepted: {error}")
        return 2
    print(f"Plan {plan.id} is active. Previous versions remain stored locally.")
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
        print(f"The session outcome could not be saved: {error}")
        return 2
    print("The session outcome has been saved. No plan was changed.")
    return 0


def run_plan_workout_evaluate(args: Namespace) -> int:
    try:
        evaluation = WorkoutEvaluationService().evaluate(session_id=args.session_id)
    except ValueError as error:
        print(f"The session could not be evaluated: {error}")
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
        print(f"The dashboard could not be created: {error}")
        return 2
    print(f"Private dashboard saved: {output_path}")
    print("Open the file in your browser. The dashboard does not change Pace data.")
    return 0


def run_home(args: Namespace, *, today: date | None = None) -> int:
    try:
        output_path = HomeService().write_home(
            end_date=args.end_date or today or date.today()
        )
    except (OSError, ValueError) as error:
        print(f"Pace Home could not be created: {error}")
        return 2
    print(f"Pace Home saved: {output_path}")
    print("Open reports/home.html. The page does not sync Garmin or change a plan.")
    return 0


def run_serve(args: Namespace) -> int:
    """Run Pace only on loopback; no cloud hosting or external access exists."""

    import uvicorn

    from pace.web.app import create_app

    try:
        initialize_database(database_url=settings.database_url)
    except Exception:
        print("The Pace database could not be initialized or upgraded.")
        return 1
    url = f"http://127.0.0.1:{args.port}"
    print(f"Pace Home is running locally at {url}")
    print("Stop it with Ctrl+C. No data is published to the internet.")
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
        print(
            "The live evaluation was not started. Add --live for six synthetic AI calls."
        )
        return 2
    api_key = resolve_openai_api_key(settings)
    if not api_key:
        print("OPENAI_API_KEY is missing; no live evaluation was run.")
        return 2
    report = CoachEvaluationService().evaluate(
        generator=OpenAIPlanClient(api_key=api_key, model=settings.openai_model)
    )
    print(json.dumps(asdict(report), default=_json_default, indent=2))
    return 0 if report.failed == 0 else 1


def run_weekly_review(args: Namespace, *, today: date | None = None) -> int:
    api_key = resolve_openai_api_key(settings)
    if not api_key:
        print("OPENAI_API_KEY is missing; no weekly review was created.")
        return 2
    try:
        path = WeeklyReviewService(
            client=WeeklyReviewClient(api_key=api_key, model=settings.openai_model)
        ).create(end_date=args.end_date or today or date.today())
    except (ValueError, PaceAIError) as error:
        print(f"The weekly review could not be created: {error}")
        return 2
    print(f"Private weekly review saved: {path}")
    print("Open the file in your browser. The review does not change the plan.")
    return 0


def run_profile_list(args: Namespace, *, today: date | None = None) -> int:
    as_of_date = args.end_date or today or date.today()
    rows = CoachingPrincipleService().list_active(as_of_date=as_of_date)
    print(
        json.dumps(
            [
                {
                    "id": item.id,
                    "statement": item.statement,
                    "source_plan_id": item.source_plan_id,
                    "review_due_date": item.review_due_date,
                    "review_due": due,
                }
                for item, due in rows
            ],
            default=_json_default,
            indent=2,
        )
    )
    return 0


def run_profile_accept(args: Namespace, *, today: date | None = None) -> int:
    try:
        item = CoachingPrincipleService().accept_from_plan(
            plan_id=args.plan_id,
            principle_index=args.principle_index,
            as_of_date=args.end_date or today or date.today(),
        )
    except ValueError as error:
        print(f"The coaching principle could not be confirmed: {error}")
        return 2
    print(f"Coaching principle {item.id} is confirmed through {item.review_due_date}.")
    return 0


def run_profile_archive(args: Namespace) -> int:
    try:
        CoachingPrincipleService().archive(principle_id=args.id)
    except ValueError as error:
        print(f"The coaching principle could not be archived: {error}")
        return 2
    print("The coaching principle has been archived.")
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
        print(f"The revised plan could not be created: {error}")
        return 2
    print(json.dumps(asdict(plan), default=_json_default, indent=2))
    if plan.status == "volume_exception_pending":
        print(
            f"Revised plan {plan.id} exceeds a base-volume boundary and is not active. "
            f"Approve the race-volume exception with "
            f"'pace plan approve-volume-exception --id {plan.id}'."
        )
    else:
        print(
            f"Revised plan {plan.id} is active. The previous plan was replaced only after "
            "successful validation."
        )
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
        print(f"The detail sync could not start: {error}")
        return 2
    except GarminRateLimitError as error:
        print(f"The detail sync stopped: {error}")
        return 3
    except GarminIntegrationError as error:
        print(f"The detail sync failed: {error}")
        return 2
    except Exception:
        print("The detail sync failed. Previously saved details were left unchanged.")
        return 1

    print(
        f"Garmin detail sync complete ({result.start_date} to {result.end_date}): "
        f"{result.candidate_activities} run/ride-kandidater, "
        f"{result.details_fetched} detail records fetched, "
        f"{result.details_inserted} new and {result.details_updated} updated."
    )
    if result.status == "partial":
        if result.stop_reason == "rate_limit":
            print(
                "The detail sync was stopped by a Garmin limit. Wait and run the same batch again."
            )
            return 3
        if result.stop_reason == "authentication":
            print(
                "The Garmin session became invalid. Log in again and run the same batch."
            )
            return 2
        print(
            "The detail sync is partially complete. Previous details were preserved; run the same batch again."
        )
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
        print(f"The race result could not be linked: {error}")
        return 2
    print("The Garmin activity is linked as a confirmed race result.")
    return 0


def run_performance_mark_benchmark(args: Namespace) -> int:
    """Store an athlete-confirmed benchmark after deterministic protocol checks."""

    try:
        PerformanceHistoryService().mark_benchmark_evidence(
            garmin_activity_id=args.garmin_activity_id,
            protocol_key=args.protocol,
        )
    except ValueError as error:
        print(f"The benchmark session could not be marked: {error}")
        return 2
    print(f"The Garmin activity has been saved as a benchmark: {args.protocol}.")
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
            ["", "Observations:", *[f"- {item}" for item in answer.observations]]
        )
    if answer.uncertainties:
        lines.extend(
            ["", "Uncertainties:", *[f"- {item}" for item in answer.uncertainties]]
        )
    if answer.knowledge_references:
        lines.extend(
            [
                "",
                "Knowledge support:",
                *[
                    f"- {item} (show: pace knowledge show --id {item})"
                    for item in answer.knowledge_references
                ],
            ]
        )
    if answer.context_event_draft is not None:
        draft = answer.context_event_draft
        duration = (
            "ongoing" if draft.ongoing else str(draft.end_date or draft.start_date)
        )
        lines.extend(
            [
                "",
                "Context draft — not saved:",
                f"- type: {draft.event_type}",
                f"- from: {draft.start_date}",
                f"- until: {duration}",
                f"- note: {draft.note}",
                "Confirm or change the details with 'pace note add'; the AI cannot save them.",
                "Copy this if the details are correct:",
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
        lines.extend(
            ["", "Observations:", *[f"- {item}" for item in answer.observations]]
        )
    if answer.uncertainties:
        lines.extend(
            ["", "Uncertainties:", *[f"- {item}" for item in answer.uncertainties]]
        )
    if answer.knowledge_references:
        lines.extend(
            [
                "",
                "Knowledge support:",
                *[
                    f"- {item} (show: pace knowledge show --id {item})"
                    for item in answer.knowledge_references
                ],
            ]
        )
    adjustment = answer.adjustment_draft
    if adjustment is not None:
        lines.extend(["", "Plan adjustment draft — not saved:"])
        labels = {
            "keep_plan": "Keep plan",
            "skip": "Skip session",
            "replace": "Replace session",
        }
        lines.extend(
            [
                f"- action: {labels[adjustment.action]}",
                f"- rationale: {adjustment.rationale}",
            ]
        )
        if adjustment.replaces_session_id is not None:
            lines.append(f"- affected session id: {adjustment.replaces_session_id}")
        if adjustment.proposed_session is not None:
            session = adjustment.proposed_session
            lines.append(
                "- proposed session: "
                f"{session.sport_type} · {session.purpose} · "
                f"{_coach_session_scope(session)} · {_coach_target_display(session)}"
            )
        lines.extend(
            [
                "The plan has not changed. To create a persistent new plan version, "
                f"first create a separate revision draft: pace plan revise --id {plan_id} --days 7",
            ]
        )
    return "\n".join(lines)


def _coach_session_scope(session) -> str:
    values = []
    if session.distance_meters is not None:
        values.append(f"{session.distance_meters / 1_000:g} km")
    if session.duration_seconds is not None:
        values.append(f"{session.duration_seconds // 60} min")
    return " · ".join(values) or "no scope"


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
    return " | ".join(values) or "no primary intensity target"


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
            print("The Pace database needs to be updated. Run: uv run pace db init")
            return 2
        raise


def _is_missing_database_schema(error: OperationalError) -> bool:
    message = str(error).lower()
    return "no such column" in message or "no such table" in message
