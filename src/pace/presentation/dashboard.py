"""Dense, local-only SVG dashboard over existing Pace facts."""

from collections import defaultdict
from datetime import timedelta
from html import escape
from pathlib import Path

from pace.config.settings import PROJECT_ROOT
from pace.planning.plan_models import TrainingPlanFact
from pace.state.models import AthleteState
from pace.timezones import athlete_local_date
from pace.trends.models import TrainingResponseTrends


DASHBOARD_PATH = PROJECT_ROOT / "reports" / "dashboard.html"


def write_dashboard_html(*, state: AthleteState, trends: TrainingResponseTrends, plan: TrainingPlanFact | None, activities, recovery_observations=None) -> Path:
    """Write the current read-only dashboard with owner-only permissions."""

    DASHBOARD_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    DASHBOARD_PATH.parent.chmod(0o700)
    DASHBOARD_PATH.write_text(
        render_dashboard_html(state=state, trends=trends, plan=plan, activities=activities, recovery_observations=recovery_observations),
        encoding="utf-8",
    )
    DASHBOARD_PATH.chmod(0o600)
    return DASHBOARD_PATH


def render_dashboard_html(*, state: AthleteState, trends: TrainingResponseTrends, plan: TrainingPlanFact | None, activities, recovery_observations=None) -> str:
    days = tuple(state.as_of_date - timedelta(days=offset) for offset in range(27, -1, -1))
    activity_seconds = defaultdict(int)
    activity_count = defaultdict(int)
    for activity in activities:
        if activity.sport_type in {"run", "ride"}:
            local_day = athlete_local_date(activity.start_time)
            activity_seconds[local_day, activity.sport_type] += activity.duration_seconds or 0
            activity_count[local_day] += 1
    observations = recovery_observations if recovery_observations is not None else state.recent_recovery_observations
    recovery = {item.date: item for item in observations}
    next_session = _next_session(plan, state.as_of_date)
    return f"""<!doctype html><html lang=\"sv\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Pace dashboard</title><style>{_STYLE}</style></head><body><main>
<header><p class=\"eyebrow\">PACE · LOKAL DASHBOARD</p><h1>{escape(state.as_of_date.isoformat())}</h1><p>Aktuell ögonblicksbild. Grafer visar lokalt lagrade fakta, inte en readiness score.</p></header>
<section class=\"cards\"><article><small>Nästa pass</small><strong>{escape(next_session)}</strong></article><article><small>Feedback, 28 dagar</small><strong>{trends.recent.outcomes.feedback_records} / {trends.recent_required_feedback_records}</strong></article><article><small>HRV-baslinje</small><strong>{_coverage(state, 'hrv')}</strong></article><article><small>Senaste Garmin-synk</small><strong>{escape(_sync_label(state))}</strong></article></section>
<section><h2>Träning · 28 dagar</h2>{_training_chart(days, activity_seconds, activity_count)}<p class=\"muted\">Y-axel: timmar per dag. X-axel: Stockholm-datum. Hovra över staplarna för råa dagsvärden.</p></section>
<section class=\"grid\"><article><h2>HRV · 28 dagar</h2>{_line_chart(days, [recovery.get(day).hrv_value if day in recovery else None for day in days], 'ms')}</article><article><h2>Vilopuls · 28 dagar</h2>{_line_chart(days, [recovery.get(day).resting_heart_rate if day in recovery else None for day in days], 'bpm')}</article><article><h2>Sömn · 28 dagar</h2>{_line_chart(days, [recovery.get(day).sleep_duration_hours if day in recovery else None for day in days], 'timmar')}</article><article><h2>Feedback & RPE</h2>{_feedback_panel(trends)}</article></section>
<section class=\"grid\"><article><h2>Aktiv kontext</h2>{_context_panel(state)}</article><article><h2>Datakvalitet</h2>{_quality_panel(state, trends)}</article></section>
<footer>Skapad lokalt av Pace. Dashboarden är läsande och ändrar aldrig plan, feedback eller kontext.</footer></main><div id=\"tooltip\" role=\"status\"></div><script>{_TOOLTIP_SCRIPT}</script></body></html>"""


def render_dashboard_fragment(
    *,
    state: AthleteState,
    trends: TrainingResponseTrends,
    plan: TrainingPlanFact | None,
    activities,
    recovery_observations=None,
) -> str:
    """Render the current dashboard facts inside Pace's shared web shell."""

    days = tuple(state.as_of_date - timedelta(days=offset) for offset in range(27, -1, -1))
    activity_seconds = defaultdict(int)
    activity_count = defaultdict(int)
    for activity in activities:
        if activity.sport_type in {"run", "ride"}:
            local_day = athlete_local_date(activity.start_time)
            activity_seconds[local_day, activity.sport_type] += activity.duration_seconds or 0
            activity_count[local_day] += 1
    observations = (
        recovery_observations
        if recovery_observations is not None
        else state.recent_recovery_observations
    )
    recovery = {item.date: item for item in observations}
    return f"""
<section class="report-metrics" aria-label="Dashboardöversikt">
  <article><span>Nästa pass</span><b>{escape(_next_session(plan, state.as_of_date))}</b></article>
  <article><span>Feedback, 28 dagar</span><b>{trends.recent.outcomes.feedback_records} / {trends.recent_required_feedback_records}</b></article>
  <article><span>HRV-baslinje</span><b>{_coverage(state, "hrv")}</b></article>
  <article><span>Senaste Garmin-synk</span><b>{escape(_sync_label(state))}</b></article>
</section>
<section class="report-section report-training">
  <h2>Träning · 28 dagar</h2>
  {_training_chart(days, activity_seconds, activity_count)}
  <p class="muted">Y-axel: timmar per dag. X-axel: Stockholm-datum. Hovra över ett värde för råa dagsvärden.</p>
</section>
<section class="report-grid four">
  <article><h2>HRV · 28 dagar</h2>{_line_chart(days, [recovery.get(day).hrv_value if day in recovery else None for day in days], "ms")}</article>
  <article><h2>Vilopuls · 28 dagar</h2>{_line_chart(days, [recovery.get(day).resting_heart_rate if day in recovery else None for day in days], "bpm")}</article>
  <article><h2>Sömn · 28 dagar</h2>{_line_chart(days, [recovery.get(day).sleep_duration_hours if day in recovery else None for day in days], "timmar")}</article>
  <article><h2>Feedback &amp; RPE</h2>{_feedback_panel(trends)}</article>
</section>
<section class="report-grid two">
  <article><h2>Aktiv kontext</h2>{_context_panel(state)}</article>
  <article><h2>Datakvalitet</h2>{_quality_panel(state, trends)}</article>
</section>"""


def _training_chart(days, activity_seconds, activity_count):
    ride_hours = [activity_seconds[day, "ride"] / 3600 for day in days]
    run_hours = [activity_seconds[day, "run"] / 3600 for day in days]
    maximum = max((*ride_hours, *run_hours), default=0) or 1
    width, height, left, bottom = 760, 260, 48, 32
    chart_height, chart_width = height - bottom - 18, width - left - 8
    step = chart_width / len(days)
    ticks = tuple(round(maximum * fraction / 4, 1) for fraction in range(5))
    grid = "".join(
        f'<line class="gridline" x1="{left}" y1="{bottom + chart_height - value / maximum * chart_height:.1f}" x2="{width - 8}" y2="{bottom + chart_height - value / maximum * chart_height:.1f}"/><text x="2" y="{bottom + chart_height - value / maximum * chart_height + 4:.1f}">{value:g} h</text>'
        for value in ticks
    )
    bars = ""
    for index, day in enumerate(days):
        x = left + index * step
        for offset, hours, css in ((0.12, ride_hours[index], "ride-bar"), (0.52, run_hours[index], "run-bar")):
            bar_height = hours / maximum * chart_height
            tooltip = f"{day.isoformat()} · Cykling: {ride_hours[index]:.2f} h · Löpning: {run_hours[index]:.2f} h · Pass: {activity_count[day]}"
            bars += f'<rect class="{css} hover-value" data-tooltip="{tooltip}" x="{x + step * offset:.1f}" y="{bottom + chart_height - bar_height:.1f}" width="{max(step * .3, 2):.1f}" height="{bar_height:.1f}"/>'
        if index % 4 == 0 or index == len(days) - 1:
            bars += f'<text class="x-label" x="{x + step / 2:.1f}" y="{height - 6}">{day.strftime("%-d/%-m")}</text>'
    return f'<p class="legend"><span class="ride-key">■</span> Cykling <span class="run-key">■</span> Löpning</p><svg class="training-chart" viewBox="0 0 {width} {height}" role="img" aria-label="Träningstimmar per dag, separerat för cykling och löpning">{grid}<line x1="{left}" y1="{bottom + chart_height}" x2="{width - 8}" y2="{bottom + chart_height}"/>{bars}</svg>'


def _line_chart(days, values, label):
    present = [value for value in values if value is not None]
    if not present:
        return '<p class="muted">Ingen lagrad data i perioden.</p>'
    low, high = min(present), max(present)
    spread = high - low or 1
    points = ' '.join(f'{16 + index * 11},{92 - (value - low) / spread * 70:.1f}' for index, value in enumerate(values) if value is not None)
    circles = ''.join(f'<circle class="hover-value" data-tooltip="{day.isoformat()}: {value:.2f} {label}" cx="{16 + index * 11}" cy="{92 - (value - low) / spread * 70:.1f}" r="4"/>' for index, (day, value) in enumerate(zip(days, values, strict=True)) if value is not None)
    return f'<svg viewBox="0 0 340 115" role="img" aria-label="{label}"><polyline points="{points}"/>{circles}<text x="0" y="112">{low:.1f}–{high:.1f} {label}</text></svg>'


def _feedback_panel(trends):
    current = trends.recent
    reasons = ', '.join(f'{escape(code)} {count}' for code, count in current.reason_counts) or 'inga registrerade'
    rpe = '—' if current.reported_rpe_average is None else f'{current.reported_rpe_average:.1f}/10 ({current.reported_rpe_data_points} pass)'
    return f'<p><b>Genomförda:</b> {current.outcomes.completed} · <b>Begränsade:</b> {current.outcomes.completed_limited} · <b>Missade:</b> {current.outcomes.skipped}</p><p><b>RPE:</b> {rpe}</p><p><b>Orsaker:</b> {reasons}</p><p class="muted">{" · ".join(trends.limitations)}</p>'


def _context_panel(state):
    if not state.relevant_context.events:
        return '<p class="muted">Ingen relevant registrerad kontext i aktuellt 7-dagarsfönster.</p>'
    return '<ul>' + ''.join(f'<li>{escape(item.event_type)} · {item.start_date}</li>' for item in state.relevant_context.events) + '</ul>'


def _quality_panel(state, trends):
    metrics = ''.join(f'<li>{escape(item.metric)}: {item.baseline_data_points}/{item.expected_baseline_days} baslinjedagar</li>' for item in state.data_quality.recovery)
    return f'<ul>{metrics}<li>Trendstatus: {escape(trends.status)}</li></ul>'


def _coverage(state, metric):
    item = next((item for item in state.data_quality.recovery if item.metric == metric), None)
    return '—' if item is None else f'{item.baseline_data_points}/{item.expected_baseline_days}'


def _sync_label(state):
    sync = state.data_quality.latest_completed_sync
    return 'saknas' if sync is None else sync.requested_end_date.isoformat() if sync.requested_end_date else sync.status


def _next_session(plan, as_of_date):
    if plan is None:
        return 'Ingen accepterad aktiv plan'
    session = next((item for item in plan.sessions if item.scheduled_date >= as_of_date), None)
    return 'Inga detaljerade pass kvar' if session is None else f'{session.scheduled_date}: {session.purpose}'


_STYLE = """body{margin:0;background:#101416;color:#ebf0ed;font:15px ui-monospace,Menlo,monospace}main{max-width:1180px;margin:auto;padding:32px}header{border-bottom:1px solid #3d5049}.eyebrow{color:#67d6ae;letter-spacing:.12em}.cards,.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px;margin:18px 0}article,section{background:#18201d;border:1px solid #30433b;border-radius:10px;padding:16px;margin:18px 0}.grid article{margin:0}small,.muted{color:#a8b8b0}strong{display:block;font-size:20px;margin-top:6px;color:#fff}svg{width:100%;height:auto;background:#111815}svg line{stroke:#50655b}svg .gridline{stroke:#26362f;stroke-dasharray:3 4}svg polyline{fill:none;stroke:#ffc857;stroke-width:3}svg circle{fill:#ffc857}svg text{fill:#a8b8b0;font-size:10px}.ride-bar{fill:#67d6ae}.run-bar{fill:#7aa7ff}.hover-value{cursor:crosshair}.ride-key{color:#67d6ae}.run-key{color:#7aa7ff}.legend{font-size:13px}.x-label{text-anchor:middle}footer{color:#a8b8b0;margin:30px 0}ul{padding-left:20px}b{color:#67d6ae}#tooltip{display:none;position:fixed;z-index:10;max-width:320px;padding:8px 10px;background:#f3f7f4;color:#101416;border-radius:6px;font:12px ui-monospace,Menlo,monospace;pointer-events:none;box-shadow:0 4px 16px #0008}"""

_TOOLTIP_SCRIPT = """const tooltip=document.getElementById('tooltip');document.querySelectorAll('.hover-value').forEach((item)=>{item.addEventListener('mouseenter',(event)=>{tooltip.textContent=item.dataset.tooltip;tooltip.style.display='block';tooltip.style.left=(event.clientX+14)+'px';tooltip.style.top=(event.clientY+14)+'px'});item.addEventListener('mousemove',(event)=>{tooltip.style.left=(event.clientX+14)+'px';tooltip.style.top=(event.clientY+14)+'px'});item.addEventListener('mouseleave',()=>{tooltip.style.display='none'})});"""
