"""Owner-only HTML rendering for an explicit weekly AI review."""

from html import escape
from pathlib import Path

from pace.config.settings import PROJECT_ROOT
from pace.weekly_review.models import WeeklyReviewAnswer


def write_weekly_review_html(*, end_date, answer: WeeklyReviewAnswer) -> Path:
    reports = PROJECT_ROOT / "reports"
    reports.mkdir(mode=0o700, parents=True, exist_ok=True)
    reports.chmod(0o700)
    path = reports / "weekly-review.html"
    path.write_text(render_weekly_review_html(end_date=end_date, answer=answer), encoding="utf-8")
    path.chmod(0o600)
    return path


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
