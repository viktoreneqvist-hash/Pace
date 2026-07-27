const embeddedState = document.getElementById("pace-state");
let state = JSON.parse(embeddedState.textContent);
const csrf = document.querySelector('meta[name="pace-csrf"]').content;
const chatLog = document.getElementById("chat-log");

const label = (value, values, fallback = "—") => values[value] || fallback;
const sport = value => label(value, {run:"Löpning", ride:"Cykel"}, value || "—");
const outcome = value => label(value, {completed:"Genomförd", completed_limited:"Begränsad", skipped:"Missad"}, "Ej rapporterad");
const ambition = value => label(value, {cautious:"Försiktig", balanced:"Balanserad", ambitious:"Offensiv"});
const role = value => label(value, {run_primary:"Löpning primär", ride_primary:"Cykling primär", balanced:"Balanserad löpning/cykling"});
const day = value => label(value, {mon:"Mån", tue:"Tis", wed:"Ons", thu:"Tor", fri:"Fre", sat:"Lör", sun:"Sön"}, value);
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[char]));

function hours(seconds) { return seconds == null ? "—" : `${Math.round(seconds / 60)} min`; }
function km(meters) { return meters == null ? "—" : `${(meters / 1000).toFixed(1).replace(".0", "")} km`; }
function addMessage(kind, body, extras = "") {
  const entry = document.createElement("article");
  entry.className = `message ${kind}`;
  entry.innerHTML = `<div class="message-meta">${kind === "athlete" ? "DU" : "PACE COACH"}</div><p>${esc(body)}</p>${extras}`;
  chatLog.append(entry);
  entry.scrollIntoView({block:"nearest", behavior:"smooth"});
}

function decisionCard(title, body, values, actionLabel, action, payload) {
  const rows = values.map(([name, value]) => `<div><span>${esc(name)}</span><b>${esc(value)}</b></div>`).join("");
  return `<article class="decision-card"><h3>${esc(title)}</h3><p>${esc(body)}</p><div class="decision-grid">${rows}</div><div class="decision-actions"><button class="primary" data-action="${action}" data-payload='${esc(JSON.stringify(payload))}'>${esc(actionLabel)}</button><button class="text-button" data-action="dismiss">Avfärda</button></div></article>`;
}

function renderState() {
  document.getElementById("today-label").textContent = state.as_of_date;
  const checkpoint = state.checkpoint;
  document.getElementById("status-strip").innerHTML = [
    ["PLANSTATUS", checkpoint.status],
    ["DETALJFÖNSTER", checkpoint.detailed_days_remaining == null ? "—" : `${checkpoint.detailed_days_remaining} dagar`],
    ["PERSONALISERING", `${state.personalization.feedback_records}/${state.personalization.required_feedback_records} feedback`],
  ].map(([name, value]) => `<div class="status-cell"><span>${name}</span><b>${esc(value)}</b></div>`).join("");
  renderPlan(); renderReports(); renderSettings(); renderRaces(); renderFacts(); renderReportLinks();
}

function renderPlan() {
  const target = document.getElementById("active-plan"); const plan = state.active_plan;
  if (!plan) { target.innerHTML = '<p class="empty">Ingen accepterad aktiv plan. Skapa ett utkast när planeringsunderlaget är klart.</p>'; return; }
  const upcoming = plan.sessions.filter(session => session.scheduled_date >= state.as_of_date).slice(0, 3);
  target.innerHTML = `<p class="notice">Plan ${plan.id} · detaljerad till ${plan.detailed_end_date}</p>` + (upcoming.length ? upcoming.map(session => `<article class="plan-session"><span class="plan-date">${esc(session.scheduled_date)} · ${sport(session.sport_type)}</span><b>${esc(session.purpose)}</b><span>${km(session.distance_meters)} · ${hours(session.duration_seconds)} · ${esc(session.target_display)}</span><span>${outcome(session.feedback_outcome)}</span></article>`).join("") : '<p class="empty">Inga detaljerade pass kvar.</p>');
}

function renderReports() {
  const target = document.getElementById("reports");
  const reports = [
    ["dashboard", "Dashboard", "Tränings- och återhämtningsgrafer"],
    ["plan", "Aktiv plan", "Det fullständiga passupplägget"],
    ["weekly_review", "Veckoreview", "Senaste AI-granskningen"],
  ];
  target.innerHTML = reports.map(([key, title, description]) => {
    const report = state.reports[key];
    if (report.available) return `<article class="report-link"><a href="${esc(report.path)}">${esc(title)} <span>↗</span></a><p>${esc(description)}</p></article>`;
    return `<article class="report-link is-unavailable"><b>${esc(title)}</b><p>${esc(report.unavailable_message)}</p></article>`;
  }).join("");
}

function renderReportLinks() {
  document.querySelectorAll("[data-report-link]").forEach(link => {
    const report = state.reports[link.dataset.reportLink];
    if (report.available) {
      link.href = report.path;
      link.removeAttribute("aria-disabled");
      link.removeAttribute("title");
      link.classList.remove("is-unavailable");
    } else {
      link.removeAttribute("href");
      link.setAttribute("aria-disabled", "true");
      link.title = report.unavailable_message;
      link.classList.add("is-unavailable");
    }
  });
}

function renderSettings() {
  const target = document.getElementById("settings"); const preference = state.preference;
  if (!preference) { target.innerHTML = '<p class="empty">Planpreferenser är inte konfigurerade.</p>'; return; }
  const days = preference.available_days.map(item => `${day(item.day)}: ${item.minutes == null ? "ingen tidsgräns" : `${item.minutes} min`}`).join(" · ");
  const zones = state.ride_zones?.map(zone => `<span class="zone">Z${zone.zone} ${zone.lower_bpm}–${zone.upper_bpm}</span>`).join("") || '<span class="empty">Inga cykelzoner</span>';
  target.innerHTML = `<div class="settings-list"><div class="setting-line"><b>${ambition(preference.coaching_ambition)}</b><span>Ambitionsläge</span></div><div class="setting-line"><b>${role(preference.sport_role)}</b><span>Sportroll</span></div><div class="setting-line"><b>${esc(days)}</b><span>Veckotillgänglighet</span></div><div class="setting-line"><div class="zone-list">${zones}</div><span>Cykelpulszoner</span></div></div>`;
}

function renderRaces() {
  const target = document.getElementById("races");
  target.innerHTML = state.races.length ? `<div class="races-list">${state.races.map(race => `<div class="setting-line"><b>${esc(race.name)} · ${esc(race.priority)}</b><span>${esc(race.race_date)} · ${sport(race.sport_type)} · taper ${esc(race.taper)}</span></div>`).join("")}</div>` : '<p class="empty">Inga kommande lopp sparade.</p>';
}

function renderFacts() {
  const target = document.getElementById("facts-grid"); const analysis = state.analysis;
  const run = analysis.sports.find(item => item.sport_type === "run"); const ride = analysis.sports.find(item => item.sport_type === "ride");
  const cells = [["TOTAL TID / 28 D", `${analysis.total_duration_hours.toFixed(1)} h`], ["LÖPNING", `${run?.activity_count || 0} pass · ${(run?.duration_hours || 0).toFixed(1)} h`], ["CYKEL", `${ride?.activity_count || 0} pass · ${(ride?.duration_hours || 0).toFixed(1)} h`], ["ÅTERHÄMTNINGSDATA", analysis.recovery_coverage.map(item => `${item[0]} ${item[1]}/${item[2]}`).join(" · ")]];
  target.innerHTML = cells.map(([name, value]) => `<article class="fact"><span>${name}</span><b>${esc(value)}</b></article>`).join("");
}

async function api(path, options = {}) {
  const response = await fetch(path, {headers:{"Content-Type":"application/json", "X-Pace-CSRF":csrf, ...(options.headers || {})}, ...options});
  const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Pace kunde inte slutföra åtgärden."); return data;
}

function responseExtras(answer) {
  let html = "";
  if (answer.observations?.length) html += `<ul>${answer.observations.map(item => `<li>${esc(item)}</li>`).join("")}</ul>`;
  if (answer.uncertainties?.length) html += `<p class="notice">Osäkerheter: ${esc(answer.uncertainties.join(" · "))}</p>`;
  if (answer.context_event_draft) { const draft = answer.context_event_draft; html += decisionCard("Context-utkast", "Pace har förberett detta. Ingenting sparas utan din bekräftelse.", [["Typ",draft.event_type],["Från",draft.start_date],["Till",draft.ongoing ? "pågående" : (draft.end_date || draft.start_date)]], "Spara context", "context", draft); }
  if (answer.feedback_draft) { const draft = answer.feedback_draft; html += decisionCard("Passutfall", "Detta är ett förslag baserat på det du skrev, inte Garmin-tolkning.", [["Utfall",outcome(draft.outcome)],["RPE",draft.perceived_exertion == null ? "—" : `${draft.perceived_exertion}/10`],["Orsak",draft.reason_code || "—"]], "Spara feedback", "feedback", draft); }
  if (answer.adjustment_draft) { const draft = answer.adjustment_draft; html += `<article class="decision-card"><h3>Planjusteringsutkast</h3><p>${esc(draft.rationale)}</p><p class="notice">Visas för granskning. Samma-dagsjusteringar sparas inte automatiskt; en riktig revision skapas i nästa UI-slice.</p></article>`; }
  return html;
}

async function submitQuestion(question) {
  addMessage("athlete", question); document.getElementById("chat-question").value = "";
  try { const answer = await api("/api/chat", {method:"POST", body:JSON.stringify({question})}); addMessage("coach", answer.answer, responseExtras(answer)); }
  catch (error) { addMessage("coach", `Kunde inte svara: ${error.message}`); }
}

document.getElementById("chat-form").addEventListener("submit", event => { event.preventDefault(); const question = document.getElementById("chat-question").value.trim(); if (question) submitQuestion(question); });
document.querySelectorAll("[data-prompt]").forEach(button => button.addEventListener("click", () => submitQuestion(button.dataset.prompt)));
document.addEventListener("click", async event => {
  const button = event.target.closest("button"); if (!button) return;
  if (button.dataset.action === "dismiss") { button.closest(".decision-card").remove(); return; }
  try {
    if (button.dataset.action === "context") { const payload = JSON.parse(button.dataset.payload); await api("/api/context/confirm", {method:"POST", body:JSON.stringify(payload)}); button.closest(".decision-card").innerHTML = "<p><b>Context sparad.</b> Pace har inte ändrat planen.</p>"; }
    if (button.dataset.action === "feedback") { const payload = JSON.parse(button.dataset.payload); await api("/api/feedback/confirm", {method:"POST", body:JSON.stringify(payload)}); button.closest(".decision-card").innerHTML = "<p><b>Feedback sparad.</b> Ingen plan har ändrats.</p>"; }
  } catch (error) { button.closest(".decision-card, .draft-card").insertAdjacentHTML("beforeend", `<p class="notice">${esc(error.message)}</p>`); }
});
async function refreshHome() { try { state = await api("/api/home", {method:"GET"}); renderState(); } catch (error) { addMessage("coach", `Kunde inte uppdatera fakta: ${error.message}`); } }
document.getElementById("refresh-home").addEventListener("click", refreshHome);
renderState();
