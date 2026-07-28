"""Owner-only HTML rendering for an explicit weekly AI review."""

import json
from dataclasses import dataclass
from datetime import date
from html import escape
from pathlib import Path

from pace.config.settings import PROJECT_ROOT
from pace.weekly_review.models import WeeklyReviewAnswer


@dataclass(frozen=True, slots=True)
class WeeklyReviewSnapshot:
    """Persisted AI output for presentation only; it is never recomputed on read."""

    end_date: date
    summary: str
    observations: tuple[str, ...]
    coach_assessment: tuple[str, ...]
    recommendations: tuple[str, ...]
    uncertainties: tuple[str, ...]


def write_weekly_review_html(
    *,
    end_date: date,
    answer: WeeklyReviewAnswer,
    reports_directory: Path = PROJECT_ROOT / "reports",
) -> Path:
    reports = reports_directory
    reports.mkdir(mode=0o700, parents=True, exist_ok=True)
    reports.chmod(0o700)
    path = reports / "weekly-review.html"
    path.write_text(render_weekly_review_html(end_date=end_date, answer=answer), encoding="utf-8")
    path.chmod(0o600)
    snapshot_path = reports / "weekly-review.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "end_date": end_date.isoformat(),
                "summary": answer.summary,
                "observations": list(answer.observations),
                "coach_assessment": list(answer.coach_assessment),
                "recommendations": list(answer.recommendations),
                "uncertainties": list(answer.uncertainties),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    snapshot_path.chmod(0o600)
    return path


def load_weekly_review_snapshot(
    *, reports_directory: Path = PROJECT_ROOT / "reports"
) -> WeeklyReviewSnapshot | None:
    """Load the latest explicit review without calling the AI service."""

    path = reports_directory / "weekly-review.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return WeeklyReviewSnapshot(
            end_date=date.fromisoformat(payload["end_date"]),
            summary=str(payload["summary"]),
            observations=tuple(str(item) for item in payload["observations"]),
            coach_assessment=tuple(str(item) for item in payload["coach_assessment"]),
            recommendations=tuple(str(item) for item in payload["recommendations"]),
            uncertainties=tuple(str(item) for item in payload["uncertainties"]),
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def render_weekly_review_fragment(snapshot: WeeklyReviewSnapshot) -> str:
    """Render an immutable review snapshot inside the shared Pace web shell."""

    def section(title: str, values: tuple[str, ...]) -> str:
        items = "".join(f"<li>{escape(value)}</li>" for value in values)
        return f"<article><h2>{escape(title)}</h2><ul>{items or '<li>Inget angivet.</li>'}</ul></article>"

    return (
        '<section class="report-section weekly-summary">'
        '<h2>Sammanfattning</h2>'
        f"<p>{escape(snapshot.summary)}</p>"
        '<p class="notice">Det här är den senaste uttryckliga AI-reviewen. '
        'Den räknas inte om när coachen sparar feedback eller context.</p>'
        "</section>"
        '<section class="report-grid two">'
        f'{section("Pace-fakta", snapshot.observations)}'
        f'{section("Coachens bedömning", snapshot.coach_assessment)}'
        f'{section("Rekommendationer", snapshot.recommendations)}'
        f'{section("Osäkerheter", snapshot.uncertainties)}'
        "</section>"
    )


def render_weekly_review_html(*, end_date, answer: WeeklyReviewAnswer) -> str:
    def section(title, values):
        items = "".join(f"<li>{escape(value)}</li>" for value in values)
        return f"<section><h2>{title}</h2><ul>{items or '<li>Inget angivet.</li>'}</ul></section>"

    return (
        '<!doctype html><html lang="sv"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Pace veckoreview</title><style>{_STYLE}</style><main>"
        f"<header><p>PACE · VECKOREVIEW</p><h1>Vecka som slutar {escape(end_date.isoformat())}</h1></header>"
        f"<section><h2>Sammanfattning</h2><p>{escape(answer.summary)}</p></section>"
        f'{section("Pace-fakta", answer.observations)}'
        f'{section("Coachens bedömning", answer.coach_assessment)}'
        f'{section("Rekommendationer", answer.recommendations)}'
        f'{section("Osäkerheter", answer.uncertainties)}'
        "<footer>Skapad genom ett explicit Pace-anrop. Rapporten ändrar inte planen.</footer>"
        "</main></html>"
    )


_STYLE = "body{margin:0;background:#101416;color:#edf2ee;font:16px system-ui}main{max-width:820px;margin:auto;padding:32px}header{border-bottom:1px solid #385147}header p{color:#67d6ae;letter-spacing:.1em}section{background:#18201d;border:1px solid #30433b;border-radius:10px;padding:16px;margin:16px 0}h1,h2{margin-top:0}li{margin:8px 0}footer{color:#a8b8b0;margin:28px 0}"
