"""Render one local entry point for Pace's current coaching loop."""

from html import escape
from pathlib import Path

from pace.config.settings import PROJECT_ROOT


HOME_PATH = PROJECT_ROOT / "reports" / "home.html"


def write_home_html(
    *,
    checkpoint,
    plan,
    personalization,
    races,
    preference,
    ride_zone_profile,
) -> Path:
    HOME_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    HOME_PATH.parent.chmod(0o700)
    HOME_PATH.write_text(
        render_home_html(
            checkpoint=checkpoint,
            plan=plan,
            personalization=personalization,
            races=races,
            preference=preference,
            ride_zone_profile=ride_zone_profile,
        ),
        encoding="utf-8",
    )
    HOME_PATH.chmod(0o600)
    return HOME_PATH


def render_home_html(
    *,
    checkpoint,
    plan,
    personalization,
    races,
    preference,
    ride_zone_profile,
) -> str:
    next_session = _next_session(plan, checkpoint.as_of_date)
    action = checkpoint.recommended_command or "Ingen planrevision behövs i dag."
    plan_link = (
        f'<a class="button" href="plan-{plan.id}.html">Öppna aktiv plan</a>'
        if plan is not None
        else ""
    )
    return f"""<!doctype html>
<html lang="sv"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pace home</title><style>{_STYLE}</style></head><body><main>
<header><p class="eyebrow">PACE · COACH HOME</p><h1>{escape(checkpoint.as_of_date.isoformat())}</h1><p>Din lokala väg från plan till pass, feedback och nästa utkast.</p></header>
<section class="cards">
<article><small>Planstatus</small><strong>{escape(checkpoint.status)}</strong><span>{escape(' · '.join(checkpoint.reasons))}</span></article>
<article><small>Nästa pass</small><strong>{escape(next_session)}</strong></article>
<article><small>Detaljfönster</small><strong>{_detail_window(checkpoint)}</strong></article>
<article><small>Personalisering</small><strong>{escape(personalization.status)}</strong><span>{personalization.feedback_records}/{personalization.required_feedback_records} feedbackposter</span></article>
</section>
<section><h2>Nästa åtgärd</h2><code>{escape(action)}</code></section>
<section><h2>Kommande lopp</h2>{_race_list(races, checkpoint.as_of_date)}</section>
<section><h2>Inställningar</h2>{_settings(preference, ride_zone_profile)}</section>
<section><h2>Observerade mönster</h2>{_patterns(personalization)}</section>
<section><h2>Rapporter</h2><div class="actions"><a class="button" href="dashboard.html">Öppna dashboard</a>{plan_link}<a class="button secondary" href="weekly-review.html">Öppna senaste veckoreview</a></div><p class="muted">En länk kan saknas tills rapporten har skapats första gången.</p></section>
<footer>Pace Home är lokal och läsande. Den synkar inte Garmin, anropar inte AI och ändrar aldrig planen.</footer>
</main></body></html>"""


def _next_session(plan, as_of_date) -> str:
    if plan is None:
        return "Ingen accepterad aktiv plan"
    session = next(
        (item for item in plan.sessions if item.scheduled_date >= as_of_date), None
    )
    if session is None:
        return "Inga detaljerade pass kvar"
    return f"{session.scheduled_date.isoformat()} · {session.purpose}"


def _detail_window(checkpoint) -> str:
    if checkpoint.detailed_end_date is None:
        return "—"
    return (
        f"{checkpoint.detailed_days_remaining} dagar kvar"
        f"<span>till {checkpoint.detailed_end_date.isoformat()}</span>"
    )


def _race_list(races, as_of_date) -> str:
    future = [race for race in races if race.race_date >= as_of_date]
    if not future:
        return '<p class="muted">Inga kommande lopp.</p>'
    return "<div class=\"race-list\">" + "".join(
        '<article class="race">'
        f'<strong>{escape(race.name)}</strong>'
        f'<span>{race.race_date.isoformat()} · prioritet {escape(race.priority)} · '
        f'{(race.race_date - as_of_date).days} dagar kvar</span></article>'
        for race in future
    ) + "</div>"


def _patterns(personalization) -> str:
    if not personalization.observed_patterns:
        return '<p class="muted">För lite explicit feedback för stabila observationer.</p>'
    return "<ul>" + "".join(
        f'<li>{escape(item.observation)} <small>({item.data_points} datapunkter)</small></li>'
        for item in personalization.observed_patterns
    ) + "</ul>"


def _settings(preference, ride_zone_profile) -> str:
    if preference is None:
        preference_html = (
            '<article class="setting wide"><small>Planpreferenser</small>'
            '<strong>Inte konfigurerade</strong>'
            '<span>Kör pace preferences set innan nästa planutkast.</span></article>'
        )
        availability_html = ""
    else:
        ambition = {
            "cautious": "Försiktig",
            "balanced": "Balanserad",
            "ambitious": "Offensiv",
        }.get(preference.coaching_ambition, preference.coaching_ambition)
        sport_role = {
            "run_primary": "Löpning primär",
            "ride_primary": "Cykling primär",
            "balanced": "Balanserad löpning/cykling",
        }.get(preference.sport_role, preference.sport_role)
        preference_html = (
            '<article class="setting"><small>Ambitionsläge</small>'
            f"<strong>{escape(ambition)}</strong></article>"
            '<article class="setting"><small>Sportroll</small>'
            f"<strong>{escape(sport_role)}</strong></article>"
        )
        availability_html = (
            '<article class="setting wide"><small>Veckotillgänglighet</small>'
            f'<div class="chips">{_availability(preference.available_days)}</div>'
            '<span>”Ingen tidsgräns” betyder att du inte har angett ett tak; '
            "det är inte tillstånd för obegränsad träning.</span></article>"
        )
    zones_html = (
        '<article class="setting wide"><small>Cykelpulszoner</small>'
        f'<div class="chips">{_zones(ride_zone_profile)}</div></article>'
    )
    return (
        '<div class="settings-grid">'
        f"{preference_html}{availability_html}{zones_html}</div>"
    )


def _availability(available_days) -> str:
    day_labels = {
        "mon": "Mån",
        "tue": "Tis",
        "wed": "Ons",
        "thu": "Tor",
        "fri": "Fre",
        "sat": "Lör",
        "sun": "Sön",
    }
    if not isinstance(available_days, list) or not available_days:
        return '<span class="chip muted-chip">Ingen tillgänglighet sparad</span>'
    items = []
    for item in available_days:
        if not isinstance(item, dict):
            continue
        day = day_labels.get(str(item.get("day")), str(item.get("day") or "—"))
        minutes = item.get("minutes")
        limit = "ingen tidsgräns" if minutes is None else f"{minutes} min"
        items.append(
            f'<span class="chip"><b>{escape(day)}</b> · {escape(limit)}</span>'
        )
    return "".join(items) or (
        '<span class="chip muted-chip">Ingen tillgänglighet sparad</span>'
    )


def _zones(ride_zone_profile) -> str:
    if ride_zone_profile is None or not isinstance(ride_zone_profile.zones, list):
        return '<span class="chip muted-chip">Inga cykelzoner sparade</span>'
    return "".join(
        '<span class="chip">'
        f'<b>Z{int(item["zone"])}</b> · {int(item["lower_bpm"])}–'
        f'{int(item["upper_bpm"])} bpm</span>'
        for item in ride_zone_profile.zones
        if isinstance(item, dict)
        and {"zone", "lower_bpm", "upper_bpm"}.issubset(item)
    )


_STYLE = """
:root{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#172027;background:#f4f6f4}body{margin:0}main{max-width:1040px;margin:auto;padding:44px 22px 64px}header{border-bottom:1px solid #d9e0db;padding-bottom:24px}.eyebrow{color:#56826a;font-size:.75rem;font-weight:750;letter-spacing:.12em}h1{font-size:clamp(2.5rem,7vw,4.8rem);letter-spacing:-.05em;margin:0}h2{margin:0 0 14px}section{background:#fff;border:1px solid #e1e6e2;border-radius:16px;margin-top:18px;padding:22px;box-shadow:0 8px 26px rgba(26,46,35,.04)}.cards{display:grid;gap:12px;grid-template-columns:repeat(4,minmax(0,1fr));background:transparent;border:0;box-shadow:none;padding:0}.cards article{background:#eaf1ec;border-radius:13px;padding:16px}.cards small,.cards span{color:#627067;display:block}.cards strong{display:block;font-size:1.05rem;margin:7px 0}.actions{display:flex;flex-wrap:wrap;gap:10px}.button{background:#295f46;border-radius:9px;color:white;font-weight:700;padding:10px 13px;text-decoration:none}.button.secondary{background:#e6eee9;color:#234b38}.race-list{display:grid;gap:9px}.race{border-left:4px solid #65aa83;padding:8px 12px}.race span{color:#627067;display:block;margin-top:3px}.settings-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.setting{background:#f3f6f3;border:1px solid #e1e8e2;border-radius:12px;padding:15px}.setting.wide{grid-column:1/-1}.setting small,.setting>span{color:#627067;display:block}.setting strong{display:block;font-size:1.1rem;margin-top:7px}.chips{display:flex;flex-wrap:wrap;gap:8px;margin:9px 0}.chip{background:#e4eee7;border-radius:999px;color:#284a38!important;display:inline-block!important;padding:7px 10px}.muted-chip{background:#edf0ed;color:#68756d!important}.muted{color:#68756d}code{background:#172027;border-radius:7px;color:#eaf5ee;display:inline-block;padding:10px 12px}li{line-height:1.5;margin-bottom:8px}footer{color:#68756d;font-size:.82rem;padding:28px 4px;text-align:center}@media(max-width:760px){.cards,.settings-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""
