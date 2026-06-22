import os
from pathlib import Path

import httpx
from dotenv import load_dotenv


SECRET_ENV_PATH = Path.home() / "Developer/secrets/running-agent.env"

load_dotenv(SECRET_ENV_PATH)

STRAVA_BASE_URL = "https://www.strava.com/api/v3"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"


def get_strava_access_token() -> str:
    access_token = os.getenv("STRAVA_ACCESS_TOKEN")

    if access_token is None:
        raise RuntimeError("Missing STRAVA_ACCESS_TOKEN in secret env file")

    return access_token


def refresh_strava_access_token() -> dict:
    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")
    refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")

    if client_id is None:
        raise RuntimeError("Missing STRAVA_CLIENT_ID in secret env file")

    if client_secret is None:
        raise RuntimeError("Missing STRAVA_CLIENT_SECRET in secret env file")

    if refresh_token is None:
        raise RuntimeError("Missing STRAVA_REFRESH_TOKEN in secret env file")

    response = httpx.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=10.0,
    )

    response.raise_for_status()

    token_data = response.json()
    update_secret_env_file(token_data)
    load_dotenv(SECRET_ENV_PATH, override=True)

    return token_data


def update_secret_env_file(token_data: dict) -> None:
    existing_values: dict[str, str] = {}

    if SECRET_ENV_PATH.exists():
        for line in SECRET_ENV_PATH.read_text().splitlines():
            if not line or line.strip().startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            existing_values[key] = value

    if "access_token" in token_data:
        existing_values["STRAVA_ACCESS_TOKEN"] = token_data["access_token"]

    if "refresh_token" in token_data:
        existing_values["STRAVA_REFRESH_TOKEN"] = token_data["refresh_token"]

    lines = [f"{key}={value}" for key, value in existing_values.items()]
    SECRET_ENV_PATH.write_text("\n".join(lines) + "\n")


def make_authenticated_get_request(
    url: str,
    params: dict | None = None,
) -> httpx.Response:
    access_token = get_strava_access_token()

    response = httpx.get(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
        timeout=10.0,
    )

    if response.status_code == 401:
        refresh_strava_access_token()
        access_token = get_strava_access_token()

        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=10.0,
        )

    response.raise_for_status()

    return response


def get_authenticated_athlete() -> dict:
    response = make_authenticated_get_request(f"{STRAVA_BASE_URL}/athlete")

    return response.json()


def get_athlete_activities(per_page: int = 100, page: int = 1) -> list[dict]:
    response = make_authenticated_get_request(
        f"{STRAVA_BASE_URL}/athlete/activities",
        params={"per_page": per_page, "page": page},
    )

    return response.json()