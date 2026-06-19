import os

import httpx
from dotenv import load_dotenv


load_dotenv()


STRAVA_BASE_URL = "https://www.strava.com/api/v3"


def get_authenticated_athlete() -> dict:
    access_token = os.getenv("STRAVA_ACCESS_TOKEN")

    if access_token is None:
        raise RuntimeError("Missing STRAVA_ACCESS_TOKEN in .env")

    response = httpx.get(
        f"{STRAVA_BASE_URL}/athlete",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()

def get_athlete_activities(per_page: int = 10) -> list[dict]:
    access_token = os.getenv("STRAVA_ACCESS_TOKEN")

    if access_token is None:
        raise RuntimeError("Missing STRAVA_ACCESS_TOKEN in .env")

    response = httpx.get(
        f"{STRAVA_BASE_URL}/athlete/activities",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"per_page": per_page},
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()