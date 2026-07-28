"""Render Pace's local web shell without exposing secrets or private notes."""

from html import escape
import json


def render_web_home(*, state: dict[str, object], csrf_token: str) -> str:
    """Return the one local Pace UI shell; dynamic content is rendered by app.js."""

    safe_state = json.dumps(state, ensure_ascii=False).replace("<", "\\u003c")
    safe_csrf = escape(csrf_token)
    return f"""<!doctype html>
<html lang="sv">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="pace-csrf" content="{safe_csrf}">
  <title>Pace — Local Coach</title>
  <link rel="stylesheet" href="/static/pace.css">
</head>
<body>
  <header class="masthead">
    <a class="wordmark" href="/">PACE<span>LOCAL COACHING SYSTEM</span></a>
    <nav class="masthead-nav" aria-label="Pace-vyer">
      <a class="nav-link is-current" href="/">Coach</a>
      <a class="nav-link" href="/dashboard">Dashboard</a>
      <a class="nav-link" href="/plan">Plan</a>
      <a class="nav-link" href="/weekly-review">Veckoreview</a>
    </nav>
    <div class="masthead-meta"><span id="today-label"></span><span>LOCAL ONLY</span></div>
  </header>
  <main class="page-grid">
    <section class="overview" aria-label="Översikt">
      <p class="kicker">OPERATIV ÖVERSIKT</p>
      <h1>Träna med fakta.<br><em>Besluta med avsikt.</em></h1>
      <div id="status-strip" class="status-strip"></div>
    </section>
    <section class="coach-panel" aria-labelledby="coach-heading">
      <div class="section-heading"><div><p class="kicker">COACHKANAL</p><h2 id="coach-heading">Dagens samtal</h2></div><span class="live-mark">● DIREKT</span></div>
      <div id="chat-log" class="chat-log" aria-live="polite"></div>
      <div class="quick-prompts" aria-label="Snabbfrågor">
        <button data-prompt="Sammanfatta vad Pace vet om min återhämtning i dag.">Återhämtning i dag</button>
        <button data-prompt="Jag kände mig ovanligt trött under dagens pass. Vad visar underlaget?">Jag var ovanligt trött</button>
        <button data-prompt="Kan jag flytta eller ändra dagens planerade pass?">Ändra dagens pass</button>
      </div>
      <form id="chat-form" class="chat-compose">
        <label for="chat-question">Prata med coachen</label>
        <textarea id="chat-question" rows="3" placeholder="Exempel: Jag genomförde passet, men RPE blev 8. Vad gör vi nu?" required></textarea>
        <div class="compose-footer"><span>Coachen skapar bara utkast. Du bekräftar varje sparad ändring.</span><button class="primary" type="submit">Skicka fråga →</button></div>
      </form>
    </section>
    <aside class="right-rail" aria-label="Plan och inställningar">
      <section class="data-panel"><p class="kicker">AKTIV PLAN</p><div id="active-plan"></div></section>
      <section class="data-panel"><p class="kicker">RAPPORTER</p><div id="reports"></div></section>
      <section class="data-panel"><p class="kicker">INSTÄLLNINGAR</p><div id="settings"></div></section>
      <section class="data-panel"><p class="kicker">KOMMANDE LOPP</p><div id="races"></div></section>
    </aside>
    <section class="facts-panel" aria-labelledby="facts-heading">
      <div class="section-heading"><div><p class="kicker">FAKTA, INTE LOAD SCORE</p><h2 id="facts-heading">Nuvarande underlag</h2></div><button id="refresh-home" class="text-button" type="button">Uppdatera fakta ↻</button></div>
      <div id="facts-grid" class="facts-grid"></div>
    </section>
  </main>
  <footer>PACE KÖRS PÅ DIN DATOR · GARMIN OCH OPENAI ANROPAS ENDAST NÄR DU UTTRYCKLIGEN BER OM DET</footer>
  <script id="pace-state" type="application/json">{safe_state}</script>
  <script src="/static/pace.js" defer></script>
</body>
</html>"""


def render_web_report_page(
    *,
    state: dict[str, object],
    active_page: str,
    kicker: str,
    title: str,
    subtitle: str,
    body_html: str,
) -> str:
    """Render an in-app report with the same persistent Pace navigation."""

    nav = "".join(
        (
            f'<a class="nav-link {"is-current" if key == active_page else ""}" '
            f'href="{href}">{label}</a>'
        )
        for key, label, href in (
            ("coach", "Coach", "/"),
            ("dashboard", "Dashboard", "/dashboard"),
            ("plan", "Plan", "/plan"),
            ("weekly_review", "Veckoreview", "/weekly-review"),
        )
    )
    as_of_date = escape(str(state["as_of_date"]))
    return f"""<!doctype html>
<html lang="sv">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pace — {escape(title)}</title>
  <link rel="stylesheet" href="/static/pace.css">
</head>
<body>
  <header class="masthead">
    <a class="wordmark" href="/">PACE<span>LOCAL COACHING SYSTEM</span></a>
    <nav class="masthead-nav" aria-label="Pace-vyer">{nav}</nav>
    <div class="masthead-meta"><span>{as_of_date}</span><span>LOCAL ONLY</span></div>
  </header>
  <main class="app-report">
    <header class="report-heading">
      <p class="kicker">{escape(kicker)}</p>
      <h1>{escape(title)}</h1>
      <p>{escape(subtitle)}</p>
    </header>
    {body_html}
  </main>
  <footer>PACE KÖRS PÅ DIN DATOR · VYN ÄR LÄSANDE OCH ÄNDRAR INTE DIN PLAN</footer>
  <div id="tooltip" role="status"></div>
  <script src="/static/report.js" defer></script>
</body>
</html>"""
