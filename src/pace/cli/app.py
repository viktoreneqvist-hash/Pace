"""Command-line entry point for the Pace application."""

from argparse import ArgumentParser, ArgumentTypeError, Namespace
from dataclasses import asdict
from datetime import date, timedelta
from getpass import getpass
import json

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig

from pace.config.settings import PROJECT_ROOT, settings
from pace.database.engine import secure_sqlite_database_file
from pace.integrations.garmin import (
    GarminAuthenticationRequiredError,
    GarminConnectClient,
    GarminIntegrationError,
    GarminRateLimitError,
)
from pace.services.garmin_sync_service import MAX_SYNC_DAYS, GarminSyncService
from pace.services.metric_service import MetricService


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


def main(argv: list[str] | None = None) -> int:
    """Run the requested Pace command and return a shell exit status."""

    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)

    if handler is None:
        parser.print_help()
        return 0

    return handler(args)
