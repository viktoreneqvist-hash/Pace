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
_FEEDBACK_REASON_LABELS = {
    "schedule": "Schema",
    "fatigue": "Trötthet",
    "pain": "Smärta",
    "illness": "Sjukdom",
    "travel": "Resa",
    "other": "Annat",
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
    "training_response_trends": "Strukturerade återkopplingstrender",
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
      <p class="muted">Varje block är en faktisk del av passet. Ett enkelt distanspass visas som ett enda block.</p>
      <div class="session-list">{''.join(_html_session_card(session) for session in sessions)}</div>
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


def render_plan_fragment(plan: TrainingPlanFact) -> str:
    """Render the accepted plan inside Pace's shared loopback UI shell."""

    sessions = _sorted_sessions(plan)
    feedback_count = sum(session.feedback_outcome is not None for session in sessions)
    ride_count = sum(session.sport_type == "ride" for session in sessions)
    run_count = sum(session.sport_type == "run" for session in sessions)
    assessment = plan.coach_assessment
    return f"""
<section class="report-metrics" aria-label="Planöversikt">
  {_metric_card("Detaljerat fönster", f"{_format_date(plan.detailed_start_date)}–{_format_date(plan.detailed_end_date)}")}
  {_metric_card("Planerade pass", str(len(sessions)))}
  {_metric_card("Cykel / löpning", f"{ride_count} / {run_count}")}
  {_metric_card("Registrerade utfall", f"{feedback_count} av {len(sessions)}")}
</section>
<section class="report-section">
  <h2>Nästa steg</h2>
  <p>{escape(_next_action_line(plan))}</p>
</section>
<section class="report-section">
  <h2>Detaljerade pass</h2>
  <p class="muted">Varje block är en faktisk del av passet. Ett enkelt distanspass visas som ett enda block.</p>
  <div class="session-list">{''.join(_html_session_card(session) for session in sessions)}</div>
</section>
<section class="report-grid two">
  <article><h2>Blocköversikt</h2><ol class="outline">{''.join(_html_outline_item(item) for item in plan.block_outline)}</ol></article>
  <article class="assessment"><h2>Coachens bedömning</h2><p class="rationale">{escape(assessment.rationale or 'Ingen coachbedömning finns för denna äldre planversion.')}</p>{_html_text_section('Slutsatser', assessment.inferences)}{_html_text_section('Osäkerheter', assessment.uncertainties)}{_html_text_section('Allmänna coachprinciper', assessment.coaching_principles)}{_html_knowledge_section(plan)}</article>
</section>
<section class="report-section">
  <h2>Faktaunderlag</h2>
  <p class="muted">Visar vilka lokala faktakategorier som användes. Vyn innehåller inte rå Garmin-data eller privata noteringstexter.</p>
  <ul>{''.join(f'<li>{escape(_fact_reference_label(reference))}</li>' for reference in assessment.fact_references) or '<li>Ingen faktakatalog finns för denna äldre planversion.</li>'}</ul>
</section>"""


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
        f"{session.purpose} · {_workout_outline(session)} · {_session_scope(session)} · {session.target_display}"
        f"{_feedback_suffix(session)}"
    )


def _session_scope(session: PlanSessionFact) -> str:
    details = [
        _format_distance(session.distance_meters),
        _format_duration(session.duration_seconds),
    ]
    return " · ".join(item for item in details if item) or "Ingen omfattning angiven"


def _workout_outline(session: PlanSessionFact) -> str:
    if not session.workout_steps:
        return "Inget detaljerat upplägg (äldre plan)"
    return " → ".join(_workout_step_outline(step) for step in session.workout_steps)


def _workout_step_outline(step) -> str:
    label = {
        "warmup": "Uppvärmning",
        "steady": "Jämn del",
        "interval": "Intervall",
        "cooldown": "Nedjogg",
    }.get(step.kind, step.kind)
    scope = " · ".join(
        value
        for value in (_format_distance(step.distance_meters), _format_duration(step.duration_seconds))
        if value
    )
    if step.kind == "interval":
        scope = f"{step.repetitions} × {scope}"
        recovery_scope = " · ".join(
            value
            for value in (
                _format_distance(step.recovery_distance_meters),
                _format_duration(step.recovery_duration_seconds),
            )
            if value
        )
        if recovery_scope:
            scope = f"{scope}, vila {recovery_scope}"
    target = _target_fact_display(step.target)
    recovery_target = (
        f", vila {_target_fact_display(step.recovery_target)}"
        if step.recovery_target is not None
        else ""
    )
    instruction = f" ({step.instruction})" if step.instruction else ""
    return f"{label}: {scope} · {target}{recovery_target}{instruction}"


def _target_fact_display(target) -> str:
    if target.kind == "rpe":
        return f"RPE {target.rpe_min}–{target.rpe_max}"
    if target.kind == "pace" and target.pace_seconds_per_km is not None:
        minutes, seconds = divmod(target.pace_seconds_per_km, 60)
        return f"{minutes}:{seconds:02d} min/km"
    if target.kind == "power" and target.power_watts is not None:
        return f"{target.power_watts} W"
    return "ingen separat intensitet"


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


def _feedback_suffix(session: PlanSessionFact) -> str:
    if session.feedback_outcome is None:
        return ""
    return f" · Utfall: {_feedback_display(session)}"


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


def _html_session_card(session: PlanSessionFact) -> str:
    steps = session.workout_steps
    blocks = (
        "".join(_html_workout_step(step) for step in steps)
        if steps
        else '<p class="muted">Inget detaljerat upplägg finns för denna äldre plan.</p>'
    )
    return (
        '<article class="session-card">'
        '<div class="session-date">'
        f'<strong>{escape(_format_date(session.scheduled_date))}</strong>'
        f'<span class="sport-chip {escape(session.sport_type)}">{escape(_sport_label(session.sport_type))}</span>'
        "</div>"
        '<div class="session-main">'
        f'<h3>{escape(session.purpose)}</h3>'
        '<div class="session-meta">'
        f'<span><b>Omfattning</b>{escape(_session_scope(session))}</span>'
        f'<span><b>Huvudmål</b>{escape(session.target_display)}</span>'
        f'<span><b>Utfall</b>{escape(_feedback_display(session))}</span>'
        "</div>"
        f'<div class="workout-blocks">{blocks}</div>'
        "</div>"
        "</article>"
    )


def _html_workout_step(step) -> str:
    label = {
        "warmup": "Uppvärmning",
        "steady": "Jämn del",
        "interval": "Intervaller",
        "cooldown": "Nedjogg",
    }.get(step.kind, step.kind)
    scope = _workout_step_scope(step)
    target = _target_fact_display(step.target)
    recovery = _html_recovery(step)
    instruction = escape(step.instruction) if step.instruction else ""
    return (
        f'<section class="workout-step {escape(step.kind)}">'
        f'<p class="step-kind">{escape(label)}</p>'
        f'<p class="step-scope">{escape(scope)}</p>'
        f'<p class="step-target">{escape(target)}</p>'
        f'{recovery}'
        f'<p class="step-instruction">{instruction}</p>'
        "</section>"
    )


def _workout_step_scope(step) -> str:
    scope = " · ".join(
        value
        for value in (_format_distance(step.distance_meters), _format_duration(step.duration_seconds))
        if value
    )
    if step.kind == "interval":
        return f"{step.repetitions} × {scope}"
    return scope or "Ingen omfattning angiven"


def _html_recovery(step) -> str:
    if step.kind != "interval":
        return ""
    recovery_scope = " · ".join(
        value
        for value in (
            _format_distance(step.recovery_distance_meters),
            _format_duration(step.recovery_duration_seconds),
        )
        if value
    )
    recovery_target = (
        _target_fact_display(step.recovery_target)
        if step.recovery_target is not None
        else "ingen separat intensitet"
    )
    return (
        '<p class="step-recovery"><b>Vila</b>'
        f"{escape(recovery_scope)} · {escape(recovery_target)}</p>"
    )


def _feedback_display(session: PlanSessionFact) -> str:
    if session.feedback_outcome is None:
        return "—"
    parts = [_OUTCOME_LABELS.get(session.feedback_outcome, session.feedback_outcome)]
    if session.feedback_perceived_exertion is not None:
        parts.append(f"RPE {session.feedback_perceived_exertion}/10")
    if session.feedback_reason_code is not None:
        parts.append(_FEEDBACK_REASON_LABELS.get(session.feedback_reason_code, session.feedback_reason_code))
    return " · ".join(parts)


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
.session-list { display: grid; gap: 14px; }.session-card { border: 1px solid #e1e6e2; border-radius: 14px; display: grid; grid-template-columns: 132px minmax(0, 1fr); overflow: hidden; }.session-date { background: #eff5f0; display: flex; flex-direction: column; gap: 10px; padding: 18px; }.session-date strong { font-size: 1rem; line-height: 1.3; }.sport-chip { align-self: flex-start; border-radius: 999px; font-size: .75rem; font-weight: 700; padding: 5px 8px; }.sport-chip.run { background: #e5edff; color: #2958ae; }.sport-chip.ride { background: #e1f3eb; color: #25714e; }.session-main { min-width: 0; padding: 18px; }.session-main h3 { font-size: 1.05rem; margin: 0 0 13px; }.session-meta { color: #536158; display: flex; flex-wrap: wrap; gap: 10px 18px; font-size: .84rem; margin-bottom: 16px; }.session-meta span { display: grid; gap: 2px; }.session-meta b { color: #7a867e; font-size: .68rem; letter-spacing: .06em; text-transform: uppercase; }.workout-blocks { display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr)); }.workout-step { background: #f7f9f7; border: 1px solid #e4eae5; border-radius: 11px; margin: 0; min-width: 0; padding: 13px; }.workout-step.interval { background: #fff8e9; border-color: #efdcae; }.step-kind { color: #5c6961; font-size: .7rem; font-weight: 700; letter-spacing: .08em; margin: 0 0 7px; text-transform: uppercase; }.step-scope { font-size: 1.05rem; font-weight: 750; margin: 0 0 3px; }.step-target { color: #35684d; font-size: .88rem; font-weight: 650; margin: 0; }.step-recovery { border-top: 1px solid #eadfc3; font-size: .82rem; margin: 10px 0 0; padding-top: 9px; }.step-recovery b { display: block; font-size: .7rem; letter-spacing: .06em; text-transform: uppercase; }.step-instruction { color: #5c6961; font-size: .8rem; line-height: 1.45; margin: 9px 0 0; }
ul, ol { line-height: 1.55; padding-left: 22px; }.outline li { margin-bottom: 13px; } footer { color: #6a756d; font-size: .82rem; padding: 28px 4px 0; text-align: center; }
@media (max-width: 720px) { main { padding: 28px 14px 48px; } section { padding: 18px; }.metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }.session-card { grid-template-columns: 1fr; }.session-date { align-items: center; flex-direction: row; justify-content: space-between; }.workout-blocks { grid-template-columns: 1fr; } }
"""
