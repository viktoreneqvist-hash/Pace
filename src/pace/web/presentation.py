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
  <link rel="stylesheet" href="/static/pace.css?v=20260729-3">
</head>
<body>
  <header class="masthead">
    <a class="wordmark" href="/">PACE<span>LOCAL COACHING SYSTEM</span></a>
    <nav class="masthead-nav" aria-label="Pace-vyer">
      <a class="nav-link is-current" href="/">Coach</a>
      <a class="nav-link" href="/dashboard">Dashboard</a>
      <a class="nav-link" href="/plan">Plan</a>
      <a class="nav-link" href="/weekly-review">Veckoreview</a>
      <a class="nav-link" href="/settings">Inställningar</a>
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
        <textarea id="chat-question" rows="3" placeholder="Fråga coachen — eller skriv /help för säkra Pace-kommandon." required></textarea>
        <div class="compose-footer"><span>Coachen skapar bara utkast. /sync och /review weekly kräver alltid bekräftelse.</span><button class="primary" type="submit">Skicka fråga →</button></div>
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
  <script src="/static/pace.js?v=20260729-2" defer></script>
</body>
</html>"""


def render_web_onboarding(*, state: dict[str, object], csrf_token: str) -> str:
    """Render a resumable first-run checklist; all writes stay same-origin."""

    safe_state = json.dumps(state, ensure_ascii=False).replace("<", "\\u003c")
    safe_csrf = escape(csrf_token)
    return f"""<!doctype html>
<html lang="sv">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="pace-csrf" content="{safe_csrf}">
  <title>Pace — Första start</title>
  <link rel="stylesheet" href="/static/pace.css?v=20260729-2">
</head>
<body>
  <header class="masthead">
    <a class="wordmark" href="/">PACE<span>LOCAL COACHING SYSTEM</span></a>
    <div class="masthead-meta"><span>FÖRSTA START</span><span>LOCAL ONLY</span></div>
  </header>
  <main class="onboarding-shell">
    <section class="onboarding-intro">
      <p class="kicker">STEG 1 AV 1 — DIN LOKALA COACH</p>
      <h1>Bygg din<br><em>utgångspunkt.</em></h1>
      <p>Pace sparar data på den här datorn. Du bestämmer om Garmin, AI och tävlingar används. Ingen plan skapas innan du väljer planmål.</p>
    </section>
    <section class="onboarding-workspace">
      <div id="setup-status" class="setup-status" aria-live="polite"></div>
      <div id="setup-error" class="setup-error" aria-live="polite"></div>
      <form id="setup-openai" class="setup-card">
        <p class="kicker">1 · AI-NYCKEL</p><h2>Aktivera coachen</h2>
        <p class="muted-copy">Din egen OpenAI-nyckel sparas endast i Paces lokala, privata inställningsfil. Den visas aldrig här igen.</p>
        <label>OpenAI API-nyckel<input name="api_key" type="password" autocomplete="off" required></label>
        <button class="primary" type="submit">Spara AI-nyckel</button>
      </form>
      <form id="setup-garmin" class="setup-card">
        <p class="kicker">2 · GARMIN</p><h2>Anslut träningsdata</h2>
        <p class="muted-copy">E-post och lösenord skickas endast till Garmin för inloggning och sparas inte av Pace. MFA-kod behövs bara om Garmin frågar.</p>
        <label>Garmin-e-post<input name="email" type="email" autocomplete="username" required></label>
        <label>Lösenord<input name="password" type="password" autocomplete="current-password" required></label>
        <label>MFA-kod (valfri)<input name="mfa_code" inputmode="numeric" autocomplete="one-time-code"></label>
        <button class="primary" type="submit">Anslut Garmin</button>
      </form>
      <form id="setup-preferences" class="setup-card wide-card">
        <p class="kicker">3 · DIN RAM</p><h2>Välj vad du faktiskt vill träna</h2>
        <div class="choice-grid" role="radiogroup" aria-label="Träningsläge">
          <label><input type="radio" name="sport_role" value="run_only" required><b>Endast löpning</b><span>Inga cykelpass.</span></label>
          <label><input type="radio" name="sport_role" value="run_primary"><b>Löpning primär</b><span>Löpning i fokus, cykel kan stötta.</span></label>
          <label><input type="radio" name="sport_role" value="balanced" checked><b>Balanserad</b><span>Coachen väljer sport utifrån fakta.</span></label>
          <label><input type="radio" name="sport_role" value="ride_primary"><b>Cykling primär</b><span>Cykling i fokus, löpning kan stötta.</span></label>
          <label><input type="radio" name="sport_role" value="ride_only"><b>Endast cykling</b><span>Inga löppass.</span></label>
        </div>
        <fieldset><legend>Ambitionsläge</legend><label><input type="radio" name="coaching_ambition" value="cautious"> Försiktig</label><label><input type="radio" name="coaching_ambition" value="balanced" checked> Balanserad</label><label><input type="radio" name="coaching_ambition" value="ambitious"> Offensiv</label></fieldset>
        <fieldset><legend>Tillgängliga dagar</legend><div class="weekday-grid">{''.join(f'<label><input type="checkbox" name="day" value="{key}:any" checked> {label}</label>' for key, label in (("mon", "Mån"), ("tue", "Tis"), ("wed", "Ons"), ("thu", "Tor"), ("fri", "Fre"), ("sat", "Lör"), ("sun", "Sön")))}</div></fieldset>
        <button class="primary" type="submit">Spara min träningsram</button>
      </form>
      <form id="setup-zones" class="setup-card wide-card">
        <p class="kicker">4 · CYKELPULS</p><h2>Bekräfta dina Garmin-zoner</h2>
        <p class="muted-copy">Behövs bara om du tillåter cykling. Ange gränser som de visas i Garmin, till exempel Z2 119–138.</p>
        <div class="zone-inputs">{''.join(f'<label>Z{number}<input name="zone_{number}" placeholder="{default}" inputmode="numeric"></label>' for number, default in ((1,"99-118"),(2,"119-138"),(3,"139-158"),(4,"159-177"),(5,"178-197")))}</div>
        <button class="primary" type="submit">Spara cykelzoner</button>
      </form>
      <section id="setup-history" class="setup-card wide-card">
        <p class="kicker">5 · UNDERLAG</p><h2>Hämta 80 dagars historik</h2>
        <p class="muted-copy">Pace importerar normalt 80 dagar i tolv sammanhängande Garmin-batcher. Varje enskild batch är högst sju dagar.</p>
        <button id="history-button" class="primary" type="button">Hämta 80 dagar från Garmin</button>
      </section>
      <form id="setup-race" class="setup-card wide-card">
        <p class="kicker">6 · VALFRITT</p><h2>Lägg till ett framtida lopp</h2>
        <p class="muted-copy">Du kan lägga till fler lopp senare. Ett lopp blir aldrig planmål förrän du väljer just det loppet när utkastet skapas.</p>
        <div class="race-inputs"><label>Namn<input name="name" placeholder="Hässlebyloppet"></label><label>Datum<input name="race_date" type="date"></label><label>Distans (km)<input name="distance_km" type="number" min="0.1" step="0.1"></label><label>Sport<select name="sport_type"><option value="run">Löpning</option><option value="ride">Cykling</option></select></label><label>Prioritet<select name="priority"><option value="A">A</option><option value="B">B</option><option value="C">C</option></select></label></div>
        <button class="secondary" type="submit">Spara lopp</button>
      </form>
      <section id="setup-plan" class="setup-card wide-card setup-final">
        <p class="kicker">7 · PLAN</p><h2>Skapa ditt första planutkast</h2>
        <p class="muted-copy">När checklistan är klar väljer du här om utkastet ska vara generellt eller riktas mot ett av dina sparade lopp. Det gör ett avsiktligt AI-anrop och skapar aldrig en accepterad plan automatiskt.</p>
        <div id="setup-plan-actions"></div>
      </section>
    </section>
  </main>
  <footer>PACE KÖRS PÅ DIN DATOR · DU KAN ÄNDRA INSTÄLLNINGAR SENARE</footer>
  <script id="pace-state" type="application/json">{safe_state}</script>
  <script src="/static/onboarding.js?v=20260729-1" defer></script>
</body>
</html>"""


def render_web_settings(*, state: dict[str, object], csrf_token: str) -> str:
    """Render settings as a first-class local view, never a terminal detour."""

    safe_state = json.dumps(state, ensure_ascii=False).replace("<", "\\u003c")
    safe_csrf = escape(csrf_token)
    return f"""<!doctype html>
<html lang="sv">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="pace-csrf" content="{safe_csrf}"><title>Pace — Inställningar</title>
  <link rel="stylesheet" href="/static/pace.css?v=20260729-3">
</head>
<body>
  <header class="masthead">
    <a class="wordmark" href="/">PACE<span>LOCAL COACHING SYSTEM</span></a>
    <nav class="masthead-nav" aria-label="Pace-vyer">
      <a class="nav-link" href="/">Coach</a><a class="nav-link" href="/dashboard">Dashboard</a><a class="nav-link" href="/plan">Plan</a><a class="nav-link" href="/weekly-review">Veckoreview</a><a class="nav-link is-current" href="/settings">Inställningar</a>
    </nav><div class="masthead-meta"><span>{escape(str(state['as_of_date']))}</span><span>LOCAL ONLY</span></div>
  </header>
  <main class="settings-shell">
    <header class="settings-heading"><p class="kicker">DIN LOKALA RAM</p><h1>Inställningar</h1><p>Ändringar gäller framtida utkast. De skriver aldrig om en accepterad plan.</p></header>
    <div id="settings-error" class="setup-error" hidden></div>
    <div id="settings-saved" class="settings-saved" hidden></div>
    <div class="settings-grid">
      <section class="setup-card"><p class="kicker">TRÄNINGSRAM</p><h2>Sport, ambition och dagar</h2>
        <form id="settings-preferences"><div id="settings-role-choices" class="choice-grid"></div><fieldset><legend>Ambitionsläge</legend><div id="settings-ambition-choices"></div></fieldset><fieldset><legend>Tillgängliga dagar</legend><div id="settings-days" class="weekday-grid"></div></fieldset><button class="primary" type="submit">Spara träningsram</button></form>
      </section>
      <section id="settings-zones-card" class="setup-card"><p class="kicker">CYKELPULS</p><h2>Garmin-zoner</h2><p class="muted-copy">Lämna cykelzonerna tomma bara om du har valt Endast löpning.</p><form id="settings-zones-form"><div id="settings-zones" class="zone-inputs"></div><button class="primary" type="submit">Spara cykelzoner</button></form></section>
      <section class="setup-card"><p class="kicker">GARMIN</p><h2>Synka träningsdata</h2><p class="muted-copy">Normal synk hämtar de senaste sju dagarna. Den längre uppdateringen läser 80 dagar för ett bättre historiskt underlag, men gör fortfarande bara säkra batcher om högst sju dagar.</p><div class="plan-action-list"><button class="primary" data-sync-days="7" type="button">Synka senaste 7 dagar</button><button class="secondary" data-sync-days="80" type="button">Uppdatera senaste 80 dagar</button></div></section>
      <section class="setup-card"><p class="kicker">KOMMANDE LOPP</p><h2>Lägg till lopp</h2><form id="settings-race-add"><div class="race-inputs"><label>Namn<input name="name" required></label><label>Datum<input name="race_date" type="date" required></label><label>Distans (km)<input name="distance_km" type="number" min="0.1" step="0.1" required></label><label>Sport<select name="sport_type"><option value="run">Löpning</option><option value="ride">Cykling</option></select></label><label>Prioritet<select name="priority"><option value="A">A</option><option value="B">B</option><option value="C">C</option></select></label></div><button class="secondary" type="submit">Spara lopp</button></form><div id="settings-races" class="settings-races"></div></section>
      <section class="setup-card"><p class="kicker">ANSLUTNINGAR</p><h2>AI och Garmin</h2><p class="muted-copy">Byt bara om du behöver ansluta ett annat konto eller ersätta din egen OpenAI-nyckel. Pace visar aldrig befintliga lösenord, token eller nycklar.</p><form id="settings-openai"><label>Ny OpenAI API-nyckel<input name="api_key" type="password" autocomplete="off" required></label><button class="text-button" type="submit">Ersätt AI-nyckel</button></form><form id="settings-garmin"><label>Garmin-e-post<input name="email" type="email" autocomplete="username" required></label><label>Lösenord<input name="password" type="password" autocomplete="current-password" required></label><label>MFA-kod (vid behov)<input name="mfa_code" autocomplete="one-time-code"></label><button class="text-button" type="submit">Anslut Garmin igen</button></form></section>
    </div>
  </main><footer>PACE KÖRS PÅ DIN DATOR · ÄNDRINGAR ÄR LOKALA</footer>
  <script id="pace-state" type="application/json">{safe_state}</script><script src="/static/settings.js?v=20260729-1" defer></script>
</body></html>"""


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
            ("settings", "Inställningar", "/settings"),
        )
    )
    as_of_date = escape(str(state["as_of_date"]))
    return f"""<!doctype html>
<html lang="sv">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pace — {escape(title)}</title>
  <link rel="stylesheet" href="/static/pace.css?v=20260729-3">
  <link rel="stylesheet" href="/static/reports.css?v=20260728-2">
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
