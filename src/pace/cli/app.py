"""Command-line entry point for the Pace application."""

from argparse import ArgumentParser, ArgumentTypeError, Namespace
from dataclasses import asdict
from datetime import date, timedelta
from getpass import getpass
import json
import shlex

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig

from pace.config.settings import PROJECT_ROOT, resolve_openai_api_key, settings
from pace.database.engine import secure_sqlite_database_file
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
from pace.services.ai_ask_service import PaceAskService
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
    race_list_parser.set_defaults(handler=run_race_list)

    race_update_parser = race_subparsers.add_parser(
        "update",
        help="ändra prioritet eller taper för ett befintligt lopp",
    )
    race_update_parser.add_argument("--id", type=int, required=True)
    race_update_parser.add_argument(
        "--priority",
        choices=sorted(SUPPORTED_RACE_PRIORITIES),
    )
    race_update_parser.add_argument(
        "--taper",
        choices=sorted(SUPPORTED_TAPER_CHOICES),
    )
    race_update_parser.set_defaults(handler=run_race_update)

    plan_parser = subparsers.add_parser(
        "plan",
        help="visa objektiva förutsättningar inför framtida planering",
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

    alembic_config = AlembicConfig(PROJECT_ROOT / "alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", settings.database_url)

    try:
        alembic_command.upgrade(alembic_config, "head")
        secure_sqlite_database_file(settings.database_url)
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
        }
        for race in races
    ]
    print(json.dumps(payload, default=_json_default, indent=2))
    return 0


def run_race_update(args: Namespace) -> int:
    """Update only the approved race priority and taper choices."""

    try:
        race = RaceService().update_race(
            race_id=args.id,
            priority=args.priority,
            taper_override=args.taper,
        )
    except ValueError as error:
        print(f"Loppet kunde inte uppdateras: {error}")
        return 2

    print(
        f"Lopp uppdaterat: {race.name}, prioritet {race.priority}, "
        f"taper {resolved_taper(race)}."
    )
    return 0


def run_plan_readiness(args: Namespace, *, today: date | None = None) -> int:
    """Print deterministic planning gates without generating a plan."""

    end_date = args.end_date or today or date.today()
    readiness = PlanReadinessService().get_readiness(as_of_date=end_date)
    print(json.dumps(asdict(readiness), default=_json_default, indent=2))
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

    return handler(args)
