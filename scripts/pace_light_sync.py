#!/usr/bin/env python3
"""Upload today's bounded Pace Light snapshot without printing private data."""

import argparse
from datetime import date
import os
import subprocess
import sys

from pace.services.pace_light_service import PaceLightService

KEYCHAIN_ACCOUNT = "pace-light"
KEYCHAIN_SERVICE = "chatgpt.site.pace-light-private.uploader"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-url", default=os.environ.get("PACE_LIGHT_SITE_URL"))
    args = parser.parse_args()
    if not args.site_url:
        print("PACE_LIGHT_SITE_URL or --site-url is required.", file=sys.stderr)
        return 2
    try:
        token = _read_keychain_token()
        if not token:
            raise ValueError("Keychain credential is empty")
        snapshot = PaceLightService().build_snapshot(as_of_date=date.today())
        PaceLightService().upload_snapshot(
            snapshot=snapshot,
            site_url=args.site_url,
            service_token=token,
        )
    except Exception as error:
        print(f"Pace Light sync failed: {error}", file=sys.stderr)
        return 1
    print("Pace Light snapshot updated.")
    return 0


def _read_keychain_token() -> str:
    result = subprocess.run(
        [
            "/usr/bin/security",
            "find-generic-password",
            "-a",
            KEYCHAIN_ACCOUNT,
            "-s",
            KEYCHAIN_SERVICE,
            "-w",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
