"""Render Pace's local web shell without exposing secrets or private notes."""

from html import escape
import json


def render_web_home(*, state: dict[str, object], csrf_token: str) -> str:
    """Return the one local Pace UI shell; dynamic content is rendered by app.js."""

    safe_state = json.dumps(state, ensure_ascii=False).replace("<", "\\u003c")
    safe_csrf = escape(csrf_token)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="pace-csrf" content="{safe_csrf}">
  <title>Pace — Local Coach</title>
  <link rel="stylesheet" href="/static/pace.css?v=20260820-1">
</head>
<body>
  <header class="masthead">
    <a class="wordmark" href="/">PACE<span>LOCAL COACHING SYSTEM</span></a>
    <nav class="masthead-nav" aria-label="Pace views">
      <a class="nav-link is-current" href="/">Coach</a>
      <a class="nav-link" href="/dashboard">Dashboard</a>
      <a class="nav-link" href="/plan">Plan</a>
      <a class="nav-link" href="/weekly-review">Weekly Review</a>
      <a class="nav-link" href="/settings">Settings</a>
    </nav>
    <div class="masthead-meta"><span id="today-label"></span><span>LOCAL ONLY</span></div>
  </header>
  <main class="page-grid">
    <section class="overview" aria-label="Overview">
      <p class="kicker">OPERATIONAL OVERVIEW</p>
      <h1>Train from evidence.<br><em>Decide with intent.</em></h1>
      <div id="status-strip" class="status-strip"></div>
    </section>
    <section class="coach-panel" aria-labelledby="coach-heading">
      <div class="section-heading"><div><p class="kicker">COACH CHANNEL</p><h2 id="coach-heading">Today's conversation</h2></div><span class="live-mark">● LIVE</span></div>
      <div id="chat-log" class="chat-log" aria-live="polite"></div>
      <div class="quick-prompts" aria-label="Quick questions">
        <button data-prompt="Summarize what Pace knows about my recovery today.">Recovery today</button>
        <button data-prompt="I felt unusually tired during today's session. What does the evidence show?">I felt unusually tired</button>
        <button data-prompt="Can I move or change today's planned session?">Change today's session</button>
      </div>
      <form id="chat-form" class="chat-compose">
        <label for="chat-question">Talk to the coach</label>
        <textarea id="chat-question" rows="3" placeholder="Ask the coach — or type /help for safe Pace commands." required></textarea>
        <div class="compose-footer"><span>The coach only proposes actions. /sync and /review weekly always require confirmation.</span><button class="primary" type="submit">Send question →</button></div>
      </form>
    </section>
    <aside class="right-rail" aria-label="Plan and settings">
      <section class="data-panel"><p class="kicker">ACTIVE PLAN</p><div id="active-plan"></div></section>
      <section class="data-panel"><p class="kicker">REPORTS</p><div id="reports"></div></section>
      <section class="data-panel"><p class="kicker">SETTINGS</p><div id="settings"></div></section>
      <section class="data-panel"><p class="kicker">UPCOMING RACES</p><div id="races"></div></section>
    </aside>
    <section class="facts-panel" aria-labelledby="facts-heading">
      <div class="section-heading"><div><p class="kicker">FACTS, NOT A LOAD SCORE</p><h2 id="facts-heading">Current evidence</h2></div><button id="refresh-home" class="text-button" type="button">Refresh facts ↻</button></div>
      <div id="facts-grid" class="facts-grid"></div>
    </section>
  </main>
  <footer>PACE RUNS ON YOUR COMPUTER · GARMIN AND OPENAI ARE CONTACTED ONLY WHEN YOU EXPLICITLY ASK</footer>
  <script id="pace-state" type="application/json">{safe_state}</script>
  <script src="/static/pace.js?v=20260915-1" defer></script>
</body>
</html>"""


def render_web_onboarding(*, state: dict[str, object], csrf_token: str) -> str:
    """Render a resumable first-run checklist; all writes stay same-origin."""

    safe_state = json.dumps(state, ensure_ascii=False).replace("<", "\\u003c")
    safe_csrf = escape(csrf_token)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="pace-csrf" content="{safe_csrf}">
  <title>Pace — First Run</title>
  <link rel="stylesheet" href="/static/pace.css?v=20260820-1">
</head>
<body>
  <header class="masthead">
    <a class="wordmark" href="/">PACE<span>LOCAL COACHING SYSTEM</span></a>
    <div class="masthead-meta"><span>FIRST RUN</span><span>LOCAL ONLY</span></div>
  </header>
  <main class="onboarding-shell">
    <section class="onboarding-intro">
      <p class="kicker">STEP 1 OF 1 — YOUR LOCAL COACH</p>
      <h1>Build your<br><em>starting point.</em></h1>
      <p>Pace stores data on this computer. You decide whether Garmin, AI, and races are used. No plan is created until you choose its goal.</p>
    </section>
    <section class="onboarding-workspace">
      <div id="setup-status" class="setup-status" aria-live="polite"></div>
      <div id="setup-error" class="setup-error" aria-live="polite"></div>
      <form id="setup-openai" class="setup-card">
        <p class="kicker">1 · AI KEY</p><h2>Enable the coach</h2>
        <p class="muted-copy">Your OpenAI key is stored only in Pace's private local settings file. It is never shown here again.</p>
        <label>OpenAI API key<input name="api_key" type="password" autocomplete="off" required></label>
        <button class="primary" type="submit">Save AI key</button>
      </form>
      <form id="setup-garmin" class="setup-card">
        <p class="kicker">2 · GARMIN</p><h2>Connect training data</h2>
        <p class="muted-copy">Your email and password are sent only to Garmin for login and are not stored by Pace. Enter an MFA code only when Garmin asks for one.</p>
        <label>Garmin email<input name="email" type="email" autocomplete="username" required></label>
        <label>Password<input name="password" type="password" autocomplete="current-password" required></label>
        <label>MFA code (optional)<input name="mfa_code" inputmode="numeric" autocomplete="one-time-code"></label>
        <button class="primary" type="submit">Connect Garmin</button>
      </form>
      <form id="setup-preferences" class="setup-card wide-card">
        <p class="kicker">3 · YOUR FRAME</p><h2>Choose what you actually want to train</h2>
        <div class="choice-grid" role="radiogroup" aria-label="Training mode">
          <label><input type="radio" name="sport_role" value="run_only" required><b>Running only</b><span>No cycling sessions.</span></label>
          <label><input type="radio" name="sport_role" value="run_primary"><b>Running primary</b><span>Running leads; cycling may support it.</span></label>
          <label><input type="radio" name="sport_role" value="balanced" checked><b>Balanced</b><span>The coach chooses the sport from the evidence.</span></label>
          <label><input type="radio" name="sport_role" value="ride_primary"><b>Cycling primary</b><span>Cycling leads; running may support it.</span></label>
          <label><input type="radio" name="sport_role" value="ride_only"><b>Cycling only</b><span>No running sessions.</span></label>
        </div>
        <fieldset><legend>Coaching ambition</legend><label><input type="radio" name="coaching_ambition" value="cautious"> Cautious</label><label><input type="radio" name="coaching_ambition" value="balanced" checked> Balanced</label><label><input type="radio" name="coaching_ambition" value="ambitious"> Ambitious</label></fieldset>
        <fieldset><legend>Available days</legend><div class="weekday-grid">{''.join(f'<label><input type="checkbox" name="day" value="{key}:any" checked> {label}</label>' for key, label in (("mon", "Mon"), ("tue", "Tue"), ("wed", "Wed"), ("thu", "Thu"), ("fri", "Fri"), ("sat", "Sat"), ("sun", "Sun")))}</div></fieldset>
        <button class="primary" type="submit">Save training frame</button>
      </form>
      <form id="setup-zones" class="setup-card wide-card">
        <p class="kicker">4 · CYCLING HEART RATE</p><h2>Confirm your Garmin zones</h2>
        <p class="muted-copy">Required only when cycling is allowed. Enter the boundaries shown in Garmin, for example Z2 119–138.</p>
        <div class="zone-inputs">{''.join(f'<label>Z{number}<input name="zone_{number}" placeholder="{default}" inputmode="numeric"></label>' for number, default in ((1,"99-118"),(2,"119-138"),(3,"139-158"),(4,"159-177"),(5,"178-197")))}</div>
        <button class="primary" type="submit">Save cycling zones</button>
      </form>
      <section id="setup-history" class="setup-card wide-card">
        <p class="kicker">5 · EVIDENCE</p><h2>Import 80 days of history</h2>
        <p class="muted-copy">Pace normally imports 80 days in twelve consecutive Garmin batches. Each individual batch covers at most seven days.</p>
        <button id="history-button" class="primary" type="button">Import 80 days from Garmin</button>
      </section>
      <form id="setup-race" class="setup-card wide-card">
        <p class="kicker">6 · OPTIONAL</p><h2>Add a future race</h2>
        <p class="muted-copy">You can add more races later. A race never becomes the plan goal until you select it when creating a plan.</p>
        <div class="race-inputs"><label>Name<input name="name" placeholder="Example 10K"></label><label>Date<input name="race_date" type="date"></label><label>Distance (km)<input name="distance_km" type="number" min="0.1" step="0.1"></label><label>Sport<select name="sport_type"><option value="run">Running</option><option value="ride">Cycling</option></select></label><label>Priority<select name="priority"><option value="A">A</option><option value="B">B</option><option value="C">C</option></select></label></div>
        <button class="secondary" type="submit">Save race</button>
      </form>
      <section id="setup-plan" class="setup-card wide-card setup-final">
        <p class="kicker">7 · PLAN</p><h2>Create your first plan</h2>
        <p class="muted-copy">Once the checklist is complete, choose whether the plan is general or directed at one saved race. Your click is the explicit authorization: Pace activates the plan only after fully validating the AI response.</p>
        <div id="setup-plan-actions"></div>
      </section>
    </section>
  </main>
  <footer>PACE RUNS ON YOUR COMPUTER · YOU CAN CHANGE SETTINGS LATER</footer>
  <script id="pace-state" type="application/json">{safe_state}</script>
  <script src="/static/onboarding.js?v=20260915-1" defer></script>
</body>
</html>"""


def render_web_settings(*, state: dict[str, object], csrf_token: str) -> str:
    """Render settings as a first-class local view, never a terminal detour."""

    safe_state = json.dumps(state, ensure_ascii=False).replace("<", "\\u003c")
    safe_csrf = escape(csrf_token)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="pace-csrf" content="{safe_csrf}"><title>Pace — Settings</title>
  <link rel="stylesheet" href="/static/pace.css?v=20260820-1">
</head>
<body>
  <header class="masthead">
    <a class="wordmark" href="/">PACE<span>LOCAL COACHING SYSTEM</span></a>
    <nav class="masthead-nav" aria-label="Pace views">
      <a class="nav-link" href="/">Coach</a><a class="nav-link" href="/dashboard">Dashboard</a><a class="nav-link" href="/plan">Plan</a><a class="nav-link" href="/weekly-review">Weekly Review</a><a class="nav-link is-current" href="/settings">Settings</a>
    </nav><div class="masthead-meta"><span>{escape(str(state['as_of_date']))}</span><span>LOCAL ONLY</span></div>
  </header>
  <main class="settings-shell">
    <header class="settings-heading"><p class="kicker">YOUR LOCAL FRAME</p><h1>Settings</h1><p>Changes apply to future plans. They never rewrite an active plan.</p></header>
    <div id="settings-error" class="setup-error" hidden></div>
    <div id="settings-saved" class="settings-saved" hidden></div>
    <div class="settings-grid">
      <section class="setup-card"><p class="kicker">TRAINING FRAME</p><h2>Sport, ambition, and days</h2>
        <form id="settings-preferences"><div id="settings-role-choices" class="choice-grid"></div><fieldset><legend>Coaching ambition</legend><div id="settings-ambition-choices"></div></fieldset><fieldset><legend>Available days</legend><div id="settings-days" class="weekday-grid"></div></fieldset><button class="primary" type="submit">Save training frame</button></form>
      </section>
      <section id="settings-zones-card" class="setup-card"><p class="kicker">CYCLING HEART RATE</p><h2>Garmin zones</h2><p class="muted-copy">Leave cycling zones empty only when Running only is selected.</p><form id="settings-zones-form"><div id="settings-zones" class="zone-inputs"></div><button class="primary" type="submit">Save cycling zones</button></form></section>
      <section class="setup-card"><p class="kicker">GARMIN</p><h2>Sync training data</h2><p class="muted-copy">A normal sync imports the latest seven days. The longer update reads 80 days for better historical evidence while still using safe batches of no more than seven days.</p><div class="plan-action-list"><button class="primary" data-sync-days="7" type="button">Sync latest 7 days</button><button class="secondary" data-sync-days="80" type="button">Update latest 80 days</button></div></section>
      <section class="setup-card"><p class="kicker">UPCOMING RACES</p><h2>Add a race</h2><form id="settings-race-add"><div class="race-inputs"><label>Name<input name="name" required></label><label>Date<input name="race_date" type="date" required></label><label>Distance (km)<input name="distance_km" type="number" min="0.1" step="0.1" required></label><label>Sport<select name="sport_type"><option value="run">Running</option><option value="ride">Cycling</option></select></label><label>Priority<select name="priority"><option value="A">A</option><option value="B">B</option><option value="C">C</option></select></label></div><button class="secondary" type="submit">Save race</button></form><div id="settings-races" class="settings-races"></div></section>
      <section class="setup-card"><p class="kicker">CONNECTIONS</p><h2>AI and Garmin</h2><p class="muted-copy">Change these only to connect another account or replace your OpenAI key. Pace never displays existing passwords, tokens, or keys.</p><form id="settings-openai"><label>New OpenAI API key<input name="api_key" type="password" autocomplete="off" required></label><button class="text-button" type="submit">Replace AI key</button></form><form id="settings-garmin"><label>Garmin email<input name="email" type="email" autocomplete="username" required></label><label>Password<input name="password" type="password" autocomplete="current-password" required></label><label>MFA code (when required)<input name="mfa_code" autocomplete="one-time-code"></label><button class="text-button" type="submit">Reconnect Garmin</button></form></section>
    </div>
  </main><footer>PACE RUNS ON YOUR COMPUTER · CHANGES STAY LOCAL</footer>
  <script id="pace-state" type="application/json">{safe_state}</script><script src="/static/settings.js?v=20260915-1" defer></script>
</body></html>"""


def render_plan_revision_control(
    *, plan_id: int, detailed_end_date: str, days_remaining: int
) -> str:
    """Render the single explicit action that extends only a due detail window."""

    timing = (
        "The detailed window has ended."
        if days_remaining == 0
        else f"{days_remaining} days remain in the detailed window."
    )
    return f"""
<section class="report-section plan-revision-control" aria-labelledby="revision-heading">
  <p class="kicker">NEXT DETAILED WINDOW</p>
  <h2 id="revision-heading">Plan the next 14 days</h2>
  <p>{escape(timing)} The current window ends {escape(detailed_end_date)}.</p>
  <p class="muted">Pace retains the block's goal and direction. It uses new Garmin data and your recorded feedback to detail the next 14 days. This plan remains unchanged if validation fails.</p>
  <div class="plan-revision-actions">
    <button class="primary" id="plan-revision-button" type="button" data-plan-id="{plan_id}">Create next 14 days</button>
    <p id="plan-revision-status" class="notice" aria-live="polite" hidden></p>
  </div>
</section>"""


def render_web_report_page(
    *,
    state: dict[str, object],
    active_page: str,
    kicker: str,
    title: str,
    subtitle: str,
    body_html: str,
    csrf_token: str | None = None,
    action_script: str | None = None,
    footer_text: str | None = None,
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
            ("weekly_review", "Weekly Review", "/weekly-review"),
            ("settings", "Settings", "/settings"),
        )
    )
    as_of_date = escape(str(state["as_of_date"]))
    csrf_meta = (
        f'<meta name="pace-csrf" content="{escape(csrf_token)}">'
        if csrf_token is not None
        else ""
    )
    action_script_tag = (
        f'<script src="{escape(action_script)}" defer></script>'
        if action_script is not None
        else ""
    )
    safe_footer = escape(
        footer_text or "PACE RUNS ON YOUR COMPUTER · THIS VIEW IS READ-ONLY AND DOES NOT CHANGE YOUR PLAN"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  {csrf_meta}
  <title>Pace — {escape(title)}</title>
  <link rel="stylesheet" href="/static/pace.css?v=20260820-1">
  <link rel="stylesheet" href="/static/reports.css?v=20260728-2">
</head>
<body>
  <header class="masthead">
    <a class="wordmark" href="/">PACE<span>LOCAL COACHING SYSTEM</span></a>
    <nav class="masthead-nav" aria-label="Pace views">{nav}</nav>
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
  <footer>{safe_footer}</footer>
  <div id="tooltip" role="status"></div>
  <script src="/static/report.js" defer></script>
  {action_script_tag}
</body>
</html>"""
