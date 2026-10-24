#!/usr/bin/env python3
"""Install a daily, read-only Pace Light snapshot upload on macOS."""

from pathlib import Path
import plistlib
import subprocess
import sys


LABEL = "com.pace.light.sync"
SITE_URL = "https://pace-light-private.flowychub.chatgpt.site"


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    uv = _find_uv()
    launch_agents = Path.home() / "Library" / "LaunchAgents"
    launch_agents.mkdir(mode=0o700, parents=True, exist_ok=True)
    plist_path = launch_agents / f"{LABEL}.plist"
    payload = {
        "Label": LABEL,
        "ProgramArguments": [
            str(uv),
            "run",
            "python",
            str(project_root / "scripts" / "pace_light_sync.py"),
            "--site-url",
            SITE_URL,
        ],
        "WorkingDirectory": str(project_root),
        "StartCalendarInterval": {"Hour": 5, "Minute": 15},
        "RunAtLoad": True,
        "StandardOutPath": "/dev/null",
        "StandardErrorPath": "/dev/null",
    }
    temporary = plist_path.with_suffix(".plist.tmp")
    with temporary.open("wb") as handle:
        plistlib.dump(payload, handle)
    temporary.chmod(0o600)
    temporary.replace(plist_path)
    user_domain = f"gui/{subprocess.check_output(['/usr/bin/id', '-u'], text=True).strip()}"
    subprocess.run(["/bin/launchctl", "bootout", user_domain, str(plist_path)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["/bin/launchctl", "bootstrap", user_domain, str(plist_path)], check=True)
    print(f"Pace Light daily sync installed for 05:15 local time: {plist_path}")
    return 0


def _find_uv() -> Path:
    result = subprocess.run(["/usr/bin/which", "uv"], check=True, capture_output=True, text=True)
    path = Path(result.stdout.strip())
    if not path.is_file():
        raise RuntimeError("uv executable was not found")
    return path


if __name__ == "__main__":
    if sys.platform != "darwin":
        raise SystemExit("Pace Light scheduling currently supports macOS only.")
    raise SystemExit(main())
