"""Render reviewable plan facts for the terminal and a private HTML report."""

from datetime import date
from html import escape
from pathlib import Path

from pace.config.settings import PROJECT_ROOT
from pace.knowledge.library import (
    KnowledgeLibraryError,
    brief_by_id,
    load_knowledge_library,
    source_by_id,
)
from pace.planning.plan_models import PlanSessionFact, TrainingPlanFact


REPORTS_DIRECTORY = PROJECT_ROOT / "reports"

_STATUS_LABELS = {
    "draft": "Utkast — inte accepterat",
    "accepted": "Accepterad",
    "superseded": "Tidigare version",
}
_OUTCOME_LABELS = {
    "completed": "Genomfört",
    "completed_limited": "Genomfört, begränsat",
    "skipped": "Inte genomfört",
}
_FACT_REFERENCE_LABELS = {
    "as_of_date": "Planeringsdatum",
    "goal": "Mål och block",
    "detailed_window": "Detaljerat planeringsfönster",
    "planning_readiness": "Garmin-historik och planeringsberedskap",
    "capacity_profile": "Faktisk träningshistorik och kontinuitet",
    "performance_readiness": "Verifierad prestationsberedskap",
    "training_preference": "Dina tillgängliga dagar och sportroll",
    "relevant_context": "Vald strukturerad kontext",
    "feedback": "Delad passåterkoppling",
    "parent_plan": "Accepterad föregående plan",
}


def render_plan_review(plan: TrainingPlanFact, *, on_date: date | None = None) -> str:
    """Return a compact Swedish terminal review without raw fact JSON."""

    reference_date = on_date or plan.as_of_date
    sessions = _sorted_sessions(plan)
    lines = [
        f"Pace plan {plan.id} — {_status_label(plan.status)}",
        _plan_period_line(plan),
        f"Detaljerat fönster: {_format_date(plan.detailed_start_date)}–{_format_date(plan.detailed_end_date)}",
        "",
        _next_session_heading(plan, sessions=sessions, on_date=reference_date),
        "",
        "Pass",
        *[_terminal_session_line(session) for session in sessions],
        "",
        "Coachens bedömning",
        plan.coach_assessment.rationale or "Ingen coachbedömning finns för denna äldre planversion.",
        *_terminal_section("Slutsatser", plan.coach_assessment.inferences),
        *_terminal_section("Osäkerheter", plan.coach_assessment.uncertainties),
        *_terminal_section("Principer", plan.coach_assessment.coaching_principles),
        *_knowledge_reference_lines(plan),
        "",
        "Faktaunderlag",
        *_fact_reference_lines(plan),
        "",
        _next_action_line(plan),
    ]
    return "\n".join(lines)


def render_plan_today(
    plan: TrainingPlanFact,
    *,
    on_date: date,
) -> str:
    """Return today's sessions, or the next scheduled session, in plain text."""

    sessions = _sorted_sessions(plan)
    today_sessions = tuple(
        session for session in sessions if session.scheduled_date == on_date
    )
    lines = [
        f"Pace idag — {_format_date(on_date)}",
        f"Plan {plan.id}: {_status_label(plan.status)}",
        "",
    ]
    if today_sessions:
        lines.extend(["Dagens pass", *[_terminal_session_line(item) for item in today_sessions]])
    else:
        future_sessions = tuple(
            session for session in sessions if session.scheduled_date > on_date
        )
        if future_sessions:
            next_session = future_sessions[0]
            lines.extend(
                [
                    "Inget pass är planerat i dag.",
                    "Nästa pass",
                    _terminal_session_line(next_session),
                ]
            )
        else:
            lines.append("Inga kommande pass finns i den här planens detaljerade fönster.")
    lines.extend(["", _next_action_line(plan)])
    return "\n".join(lines)


def select_plan_for_today(
    plans: tuple[TrainingPlanFact, ...],
    *,
    on_date: date,
    plan_id: int | None,
) -> TrainingPlanFact:
    """Select an explicitly named plan or the active accepted plan for a day."""

    if plan_id is not None:
        for plan in plans:
            if plan.id == plan_id:
                return plan
        raise ValueError(f"No plan exists with id {plan_id}.")
    active_plans = tuple(
        plan
        for plan in plans
        if plan.status == "accepted"
        and plan.block_start_date <= on_date <= plan.block_end_date
    )
    if not active_plans:
        raise ValueError(
            "No accepted plan is active today. Use --id to preview a draft plan."
        )
    return max(active_plans, key=lambda plan: plan.id)


def write_plan_html_report(
    plan: TrainingPlanFact,
    *,
    reports_directory: Path = REPORTS_DIRECTORY,
) -> Path:
    """Write a private local HTML view without notes, raw payloads, or AI calls."""

    reports_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if reports_directory.stat().st_mode & 0o777 != 0o700:
        reports_directory.chmod(0o700)
    output_path = reports_directory / f"plan-{plan.id}.html"
    output_path.write_text(render_plan_html(plan), encoding="utf-8")
    output_path.chmod(0o600)
    return output_path


def render_plan_html(plan: TrainingPlanFact) -> str:
    """Render a self-contained report suitable for opening directly in a browser."""

    sessions = _sorted_sessions(plan)
    feedback_count = sum(session.feedback_outcome is not None for session in sessions)
    ride_count = sum(session.sport_type == "ride" for session in sessions)
    run_count = sum(session.sport_type == "run" for session in sessions)
    assessment = plan.coach_assessment
    return f"""<!doctype html>
<html lang="sv">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pace – plan {plan.id}</title>
  <style>{_HTML_STYLE}</style>
</head>
<body>
  <main>
    <header>
      <p class="eyebrow">PACE · LOKAL PLANRAPPORT</p>
      <h1>Plan {plan.id}</h1>
      <p class="status {_status_class(plan.status)}">{escape(_status_label(plan.status))}</p>
      <p class="subtitle">{escape(_plan_period_line(plan))}</p>
    </header>
    <section class="metrics" aria-label="Planöversikt">
      {_metric_card("Detaljerat fönster", f"{_format_date(plan.detailed_start_date)}–{_format_date(plan.detailed_end_date)}")}
      {_metric_card("Planerade pass", str(len(sessions)))}
      {_metric_card("Cykel / löpning", f"{ride_count} / {run_count}")}
      {_metric_card("Registrerade utfall", f"{feedback_count} av {len(sessions)}")}
    </section>
    <section>
      <h2>Nästa steg</h2>
      <p>{escape(_next_action_line(plan))}</p>
    </section>
    <section>
      <h2>Detaljerade pass</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Datum</th><th>Sport</th><th>Pass</th><th>Omfattning</th><th>Mål</th><th>Utfall</th></tr></thead>
          <tbody>{''.join(_html_session_row(session) for session in sessions)}</tbody>
        </table>
      </div>
    </section>
    <section>
      <h2>Blocköversikt</h2>
      <ol class="outline">{''.join(_html_outline_item(item) for item in plan.block_outline)}</ol>
    </section>
    <section class="assessment">
      <h2>Coachens bedömning</h2>
      <p class="rationale">{escape(assessment.rationale or 'Ingen coachbedömning finns för denna äldre planversion.')}</p>
      {_html_text_section('Slutsatser', assessment.inferences)}
      {_html_text_section('Osäkerheter', assessment.uncertainties)}
      {_html_text_section('Allmänna coachprinciper', assessment.coaching_principles)}
      {_html_knowledge_section(plan)}
    </section>
    <section>
      <h2>Faktaunderlag</h2>
      <p class="muted">Rapporten visar vilka lokala faktakategorier som användes. Den innehåller inte rå Garmin-data eller privata noteringstexter.</p>
      <ul>{''.join(f'<li>{escape(_fact_reference_label(reference))}</li>' for reference in assessment.fact_references) or '<li>Ingen faktakatalog finns för denna äldre planversion.</li>'}</ul>
    </section>
    <footer>Skapad lokalt av Pace. Rapporten är en läsvy och ändrar inte planen.</footer>
  </main>
</body>
</html>
"""


def _sorted_sessions(plan: TrainingPlanFact) -> tuple[PlanSessionFact, ...]:
    return tuple(sorted(plan.sessions, key=lambda item: (item.scheduled_date, item.id)))


def _plan_period_line(plan: TrainingPlanFact) -> str:
    goal = "Allmänt träningsmål" if plan.goal_mode == "general" else "Tävlingsblock"
    return f"{goal} · {_format_date(plan.block_start_date)}–{_format_date(plan.block_end_date)}"


def _next_session_heading(
    plan: TrainingPlanFact,
    *,
    sessions: tuple[PlanSessionFact, ...],
    on_date: date,
) -> str:
    matching = tuple(session for session in sessions if session.scheduled_date >= on_date)
    if not matching:
        return "Inga återstående pass finns i det detaljerade fönstret."
    prefix = "Dagens första pass" if matching[0].scheduled_date == on_date else "Nästa pass"
    return f"{prefix}: {_terminal_session_line(matching[0])}"


def _terminal_session_line(session: PlanSessionFact) -> str:
    return (
        f"- {_format_date(session.scheduled_date)} · {_sport_label(session.sport_type)} · "
        f"{session.purpose} · {_session_scope(session)} · {session.target_display}"
        f"{_feedback_suffix(session.feedback_outcome)}"
    )


def _session_scope(session: PlanSessionFact) -> str:
    details = [
        _format_distance(session.distance_meters),
        _format_duration(session.duration_seconds),
    ]
    return " · ".join(item for item in details if item) or "Ingen omfattning angiven"


def _format_date(value: date) -> str:
    return value.strftime("%-d %b %Y")


def _format_distance(value: float | None) -> str:
    if value is None:
        return ""
    distance_km = value / 1_000
    return f"{distance_km:g} km"


def _format_duration(value: int | None) -> str:
    if value is None:
        return ""
    hours, remainder = divmod(value, 3_600)
    minutes = remainder // 60
    if hours:
        return f"{hours} h {minutes} min"
    return f"{minutes} min"


def _sport_label(sport_type: str) -> str:
    return {"ride": "Cykel", "run": "Löpning"}.get(sport_type, sport_type)


def _status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, status)


def _feedback_suffix(outcome: str | None) -> str:
    if outcome is None:
        return ""
    return f" · Utfall: {_OUTCOME_LABELS.get(outcome, outcome)}"


def _terminal_section(title: str, items: tuple[str, ...]) -> list[str]:
    if not items:
        return []
    return ["", title, *(f"- {item}" for item in items)]


def _fact_reference_lines(plan: TrainingPlanFact) -> list[str]:
    references = plan.coach_assessment.fact_references
    if not references:
        return ["- Ingen faktakatalog finns för denna äldre planversion."]
    return [f"- {_fact_reference_label(reference)}" for reference in references]


def _knowledge_reference_lines(plan: TrainingPlanFact) -> list[str]:
    references = plan.coach_assessment.knowledge_references
    if not references:
        return []
    return ["", "Kunskapsstöd", *_knowledge_display_lines(references)]


def _knowledge_display_lines(references: tuple[str, ...]) -> list[str]:
    try:
        library = load_knowledge_library()
    except KnowledgeLibraryError:
        return [f"- {reference}" for reference in references]
    lines = []
    for reference in references:
        brief = brief_by_id(library, brief_id=reference)
        if brief is None:
            lines.append(f"- {reference}")
            continue
        source_titles = [
            source.title
            for source_id in brief.source_ids
            if (source := source_by_id(library, source_id=source_id)) is not None
        ]
        suffix = f" — {'; '.join(source_titles)}" if source_titles else ""
        lines.append(f"- {brief.title}{suffix}")
    return lines


def _html_knowledge_section(plan: TrainingPlanFact) -> str:
    references = plan.coach_assessment.knowledge_references
    if not references:
        return ""
    lines = _knowledge_display_lines(references)
    items = "".join(f"<li>{escape(line.removeprefix('- '))}</li>" for line in lines)
    return (
        "<h3>Kunskapsstöd</h3>"
        "<p class=\"muted\">Källstöd för principerna, inte en ersättning för dina lokala fakta.</p>"
        f"<ul>{items}</ul>"
    )


def _fact_reference_label(reference: str) -> str:
    return _FACT_REFERENCE_LABELS.get(reference, reference.replace("_", " ").capitalize())


def _next_action_line(plan: TrainingPlanFact) -> str:
    if plan.status == "draft":
        return f"Granska och acceptera vid behov: pace plan accept --id {plan.id}"
    if plan.status == "accepted":
        return "Registrera utfall efter ett pass: pace plan feedback --session-id <id> --outcome completed"
    return "Detta är en tidigare planversion och kan läsas, men inte ändras."


def _metric_card(label: str, value: str) -> str:
    return f'<div class="metric"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>'


def _html_session_row(session: PlanSessionFact) -> str:
    outcome = "—" if session.feedback_outcome is None else _OUTCOME_LABELS.get(
        session.feedback_outcome, session.feedback_outcome
    )
    return (
        "<tr>"
        f"<td>{escape(_format_date(session.scheduled_date))}</td>"
        f"<td>{escape(_sport_label(session.sport_type))}</td>"
        f"<td>{escape(session.purpose)}</td>"
        f"<td>{escape(_session_scope(session))}</td>"
        f"<td>{escape(session.target_display)}</td>"
        f"<td>{escape(outcome)}</td>"
        "</tr>"
    )


def _html_outline_item(item: dict[str, object]) -> str:
    start = escape(str(item.get("week_start", "")))
    end = escape(str(item.get("week_end", "")))
    focus = escape(str(item.get("focus", "")))
    return f"<li><strong>{start}–{end}</strong><br>{focus}</li>"


def _html_text_section(title: str, items: tuple[str, ...]) -> str:
    if not items:
        return ""
    return f"<h3>{escape(title)}</h3><ul>{''.join(f'<li>{escape(item)}</li>' for item in items)}</ul>"


def _status_class(status: str) -> str:
    return {"draft": "draft", "accepted": "accepted", "superseded": "superseded"}.get(
        status, "superseded"
    )


_HTML_STYLE = """
:root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, sans-serif; color: #172027; background: #f4f6f4; }
body { margin: 0; background: #f4f6f4; }
main { max-width: 960px; margin: 0 auto; padding: 48px 24px 64px; }
header { border-bottom: 1px solid #d9e0db; padding-bottom: 28px; }
.eyebrow { color: #56826a; font-size: .75rem; font-weight: 700; letter-spacing: .12em; margin: 0 0 12px; }
h1 { font-size: clamp(2.4rem, 7vw, 4.5rem); letter-spacing: -.05em; margin: 0; }
h2 { margin: 0 0 14px; font-size: 1.35rem; letter-spacing: -.02em; }
h3 { margin: 22px 0 8px; font-size: 1rem; }
section { background: #fff; border: 1px solid #e1e6e2; border-radius: 16px; margin-top: 20px; padding: 24px; box-shadow: 0 8px 26px rgba(26, 46, 35, .04); }
.status { display: inline-block; border-radius: 999px; font-size: .9rem; font-weight: 700; margin: 16px 0 0; padding: 7px 11px; }
.status.draft { background: #fff1c4; color: #715501; }.status.accepted { background: #dcefe2; color: #1f663d; }.status.superseded { background: #e8ece9; color: #59645e; }
.subtitle, .muted { color: #5c6961; }.rationale { font-size: 1.12rem; line-height: 1.6; }
.metrics { display: grid; gap: 12px; grid-template-columns: repeat(4, minmax(0, 1fr)); background: transparent; border: 0; box-shadow: none; padding: 0; }
.metric { background: #e6f0e9; border-radius: 14px; min-height: 90px; padding: 18px; }.metric span { color: #536158; display: block; font-size: .82rem; }.metric strong { display: block; font-size: 1.15rem; margin-top: 8px; }
.table-wrap { overflow-x: auto; } table { border-collapse: collapse; min-width: 760px; width: 100%; } th { color: #5b675f; font-size: .75rem; letter-spacing: .06em; text-align: left; text-transform: uppercase; } td, th { border-bottom: 1px solid #e5e9e6; padding: 12px 8px; vertical-align: top; } td:nth-child(3) { min-width: 230px; }
ul, ol { line-height: 1.55; padding-left: 22px; }.outline li { margin-bottom: 13px; } footer { color: #6a756d; font-size: .82rem; padding: 28px 4px 0; text-align: center; }
@media (max-width: 720px) { main { padding: 28px 14px 48px; } section { padding: 18px; }.metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
"""
