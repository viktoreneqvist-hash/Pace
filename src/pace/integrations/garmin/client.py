"""Small, Pace-owned boundary around the Garmin Connect library.

Only this module imports ``garminconnect``. That keeps provider-specific
authentication and error types out of the rest of the application.
"""

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)


# This public filename identifies a session file; the value is not a credential.
GARMIN_TOKEN_FILENAME = "garmin_tokens.json"  # nosec B105


class GarminIntegrationError(RuntimeError):
    """A provider failure Pace can present safely to the CLI."""


class GarminAuthenticationRequiredError(GarminIntegrationError):
    """No valid saved Garmin session is available."""


class GarminRateLimitError(GarminIntegrationError):
    """Garmin has asked Pace to stop making requests for now."""


def prepare_token_directory(token_dir: Path) -> Path:
    """Create the private directory that holds Garmin refresh tokens."""

    expanded_dir = token_dir.expanduser()
    created_directories: list[Path] = []
    candidate = expanded_dir
    while not candidate.exists():
        created_directories.append(candidate)
        candidate = candidate.parent
    expanded_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    for created_directory in created_directories:
        created_directory.chmod(0o700)
    expanded_dir.chmod(0o700)
    return expanded_dir


def secure_token_file(token_dir: Path) -> None:
    """Keep Garmin's known token file owner-readable and owner-writable only."""

    token_file = token_dir / GARMIN_TOKEN_FILENAME
    if token_file.is_file() and token_file.stat().st_mode & 0o777 != 0o600:
        token_file.chmod(0o600)


def require_secure_token_file(token_dir: Path) -> None:
    """Verify that Garmin persisted a reusable token with private permissions."""

    token_file = token_dir / GARMIN_TOKEN_FILENAME
    if not token_file.is_file():
        raise GarminIntegrationError(
            "The Garmin session could not be saved locally. Check file "
            "permissions and available disk space."
        )

    try:
        secure_token_file(token_dir)
    except OSError as error:
        raise GarminIntegrationError(
            "The local Garmin session token file could not be secured."
        ) from error


def persist_secure_token_file(api: Garmin, token_dir: Path) -> None:
    """Persist authenticated in-memory tokens without suppressing write errors."""

    try:
        api.client.dump(str(token_dir))
    except Exception as error:
        raise GarminIntegrationError(
            "The Garmin session could not be saved locally. Check file "
            "permissions and available disk space."
        ) from error

    require_secure_token_file(token_dir)


class GarminConnectClient:
    """Authenticate with Garmin and retrieve provider payloads.

    ``garminconnect`` writes ``garmin_tokens.json`` inside the supplied
    directory with owner-only permissions. Pace supplies the directory but
    never reads, prints, or stores the token contents itself.
    """

    def __init__(self, api: Garmin, token_dir: Path) -> None:
        self._api = api
        self._token_dir = prepare_token_directory(token_dir)

    @classmethod
    def login_with_credentials(
        cls,
        *,
        email: str,
        password: str,
        token_dir: Path,
        prompt_mfa: Callable[[], str],
    ) -> "GarminConnectClient":
        """Log in once and persist a reusable Garmin session token."""

        api = Garmin(email=email, password=password, prompt_mfa=prompt_mfa)
        client = cls(api, token_dir)

        try:
            api.login(str(client._token_dir))
        except GarminConnectTooManyRequestsError as error:
            raise GarminRateLimitError(
                "Garmin is rate-limiting login attempts. Wait and try again later."
            ) from error
        except GarminConnectAuthenticationError as error:
            raise GarminAuthenticationRequiredError(
                "Garmin could not verify the login. Check the email, password, and MFA code."
            ) from error
        except GarminConnectConnectionError as error:
            raise GarminIntegrationError(
                "Could not connect to Garmin. Check the network and try again."
            ) from error

        persist_secure_token_file(api, client._token_dir)
        return client

    @classmethod
    def from_saved_tokens(cls, token_dir: Path) -> "GarminConnectClient":
        """Restore a saved Garmin session without asking for a password."""

        private_token_dir = prepare_token_directory(token_dir)
        if not (private_token_dir / GARMIN_TOKEN_FILENAME).is_file():
            raise GarminAuthenticationRequiredError(
                "No valid Garmin session exists locally. Run 'pace garmin login' first."
            )

        api = Garmin()
        client = cls(api, private_token_dir)
        require_secure_token_file(client._token_dir)

        try:
            api.login(str(client._token_dir))
        except GarminConnectTooManyRequestsError as error:
            raise GarminRateLimitError(
                "Garmin is rate-limiting requests. Wait and run the sync again later."
            ) from error
        except GarminConnectAuthenticationError as error:
            raise GarminAuthenticationRequiredError(
                "No valid Garmin session exists locally. Run 'pace garmin login' first."
            ) from error
        except GarminConnectConnectionError as error:
            raise GarminIntegrationError(
                "Could not restore the Garmin session because of a "
                "connection error. Try again later."
            ) from error

        persist_secure_token_file(api, client._token_dir)
        return client

    def get_activities(
        self,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch activities in an inclusive calendar-date window."""

        try:
            return self._api.get_activities_by_date(
                start_date.isoformat(),
                end_date.isoformat(),
            )
        except GarminConnectTooManyRequestsError as error:
            raise GarminRateLimitError(
                "Garmin is rate-limiting requests. Wait and run the sync again later."
            ) from error
        except GarminConnectAuthenticationError as error:
            raise GarminAuthenticationRequiredError(
                "The Garmin session is no longer valid. Run 'pace garmin login' again."
            ) from error
        except GarminConnectConnectionError as error:
            raise GarminIntegrationError(
                "Could not fetch activities from Garmin. Try again later."
            ) from error

    def get_activity_performance_detail(self, activity_id: str) -> dict[str, Any]:
        """Fetch a scalar activity detail response without route or chart data."""

        return self._call_activity_endpoint(
            "activity details",
            self._api.get_activity_details,
            activity_id,
            maxchart=1,
            maxpoly=0,
        )

    def get_activity_splits(self, activity_id: str) -> dict[str, Any]:
        """Fetch Garmin's split summaries for one already imported activity."""

        return self._call_activity_endpoint(
            "activity splits",
            self._api.get_activity_splits,
            activity_id,
        )

    def get_activity_heart_rate_zones(
        self, activity_id: str
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Fetch aggregate time in heart-rate zones for one activity."""

        return self._call_activity_endpoint(
            "activity heart-rate zones",
            self._api.get_activity_hr_in_timezones,
            activity_id,
        )

    def upload_planned_workout(self, workout: Any, *, sport_type: str) -> dict[str, Any]:
        """Upload one typed Pace workout after an explicit athlete confirmation."""

        method = (
            self._api.upload_running_workout
            if sport_type == "run"
            else self._api.upload_cycling_workout
        )
        return self._call_workout_endpoint("upload the workout", method, workout)

    def schedule_workout(self, workout_id: str, scheduled_date: date) -> dict[str, Any]:
        """Put an uploaded workout on the Garmin calendar."""

        return self._call_workout_endpoint(
            "schedule the workout",
            self._api.schedule_workout,
            workout_id,
            scheduled_date.isoformat(),
        )

    def push_workout_to_device(self, workout_id: str) -> dict[str, Any]:
        """Ask Garmin to send one workout to the athlete's last-used device."""

        return self._call_workout_endpoint(
            "send the workout to the device",
            self._api.push_workout_to_device,
            workout_id,
        )

    def get_daily_summary(self, metric_date: date) -> dict[str, Any]:
        """Fetch Garmin's daily summary, including resting HR and stress."""

        return self._call_daily_endpoint(
            "the daily summary",
            self._api.get_user_summary,
            metric_date,
        )

    def get_sleep_data(self, metric_date: date) -> dict[str, Any]:
        """Fetch the detailed nightly sleep summary for one calendar day."""

        return self._call_daily_endpoint(
            "sleep data",
            self._api.get_sleep_data,
            metric_date,
        )

    def get_hrv_data(self, metric_date: date) -> dict[str, Any] | None:
        """Fetch HRV data when the connected Garmin device provides it."""

        return self._call_daily_endpoint(
            "HRV-data",
            self._api.get_hrv_data,
            metric_date,
        )

    def get_training_readiness(self, metric_date: date) -> list[dict[str, Any]]:
        """Fetch one or more Garmin training-readiness snapshots for a day."""

        return self._call_daily_endpoint(
            "training readiness",
            self._api.get_training_readiness,
            metric_date,
        )

    def _call_daily_endpoint(self, label: str, method, metric_date: date):
        """Translate provider failures consistently for daily recovery calls."""

        try:
            return method(metric_date.isoformat())
        except GarminConnectTooManyRequestsError as error:
            raise GarminRateLimitError(
                "Garmin is rate-limiting requests. Wait and run the sync again later."
            ) from error
        except GarminConnectAuthenticationError as error:
            raise GarminAuthenticationRequiredError(
                "The Garmin session is no longer valid. Run 'pace garmin login' again."
            ) from error
        except GarminConnectConnectionError as error:
            raise GarminIntegrationError(
                f"Could not fetch {label} from Garmin. Try again later."
            ) from error

    def _call_activity_endpoint(self, label: str, method, activity_id: str, **kwargs):
        """Translate provider failures consistently for bounded detail calls."""

        try:
            return method(activity_id, **kwargs)
        except GarminConnectTooManyRequestsError as error:
            raise GarminRateLimitError(
                "Garmin is rate-limiting requests. Wait and run the same detail batch again later."
            ) from error
        except GarminConnectAuthenticationError as error:
            raise GarminAuthenticationRequiredError(
                "The Garmin session is no longer valid. Run 'pace garmin login' again."
            ) from error
        except GarminConnectConnectionError as error:
            raise GarminIntegrationError(
                f"Could not fetch {label} from Garmin. Try again later."
            ) from error

    def _call_workout_endpoint(self, label: str, method, *args):
        """Translate provider failures without exposing credentials or payloads."""

        try:
            return method(*args)
        except GarminConnectTooManyRequestsError as error:
            raise GarminRateLimitError(
                "Garmin is rate-limiting workout requests. Wait and try again later."
            ) from error
        except GarminConnectAuthenticationError as error:
            raise GarminAuthenticationRequiredError(
                "The Garmin session is no longer valid. Connect Garmin again."
            ) from error
        except GarminConnectConnectionError as error:
            raise GarminIntegrationError(
                f"Could not {label} in Garmin. Try again later."
            ) from error
