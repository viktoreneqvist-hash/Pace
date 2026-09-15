const embeddedState = document.getElementById("pace-state");
let state = JSON.parse(embeddedState.textContent);
const csrf = document.querySelector('meta[name="pace-csrf"]').content;
const chatLog = document.getElementById("chat-log");

const label = (value, values, fallback = "—") => values[value] || fallback;
const sport = value => label(value, {run:"Running", ride:"Cycling"}, value || "—");
const outcome = value => label(value, {completed:"Completed", completed_limited:"Limited", skipped:"Skipped"}, "Not reported");
const ambition = value => label(value, {cautious:"Cautious", balanced:"Balanced", ambitious:"Ambitious"});
const role = value => label(value, {run_only:"Running only", run_primary:"Running primary", ride_primary:"Cycling primary", ride_only:"Cycling only", balanced:"Balanced running/cycling"});
const day = value => label(value, {mon:"Mon", tue:"Tue", wed:"Wed", thu:"Thu", fri:"Fri", sat:"Sat", sun:"Sun"}, value);
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[char]));

function hours(seconds) { return seconds == null ? "—" : `${Math.round(seconds / 60)} min`; }
function km(meters) { return meters == null ? "—" : `${(meters / 1000).toFixed(1).replace(".0", "")} km`; }
function addMessage(kind, body, extras = "") {
  const entry = document.createElement("article");
  entry.className = `message ${kind}`;
  entry.innerHTML = `<div class="message-meta">${kind === "athlete" ? "YOU" : "PACE COACH"}</div><p>${esc(body)}</p>${extras}`;
  chatLog.append(entry);
  entry.scrollIntoView({block:"nearest", behavior:"smooth"});
}

function restoreConversation() {
  if (!Array.isArray(state.conversation) || chatLog.children.length) return;
  state.conversation.forEach(message => {
    if (message && (message.role === "athlete" || message.role === "coach") && typeof message.text === "string") {
      addMessage(message.role, message.text);
    }
  });
}

function decisionCard(title, body, values, actionLabel, action, payload) {
  const rows = values.map(([name, value]) => `<div><span>${esc(name)}</span><b>${esc(value)}</b></div>`).join("");
  return `<article class="decision-card"><h3>${esc(title)}</h3><p>${esc(body)}</p><div class="decision-grid">${rows}</div><div class="decision-actions"><button class="primary" data-action="${action}" data-payload='${esc(JSON.stringify(payload))}'>${esc(actionLabel)}</button><button class="text-button" data-action="dismiss">Dismiss</button></div></article>`;
}

function renderState() {
  document.getElementById("today-label").textContent = state.as_of_date;
  const checkpoint = state.checkpoint;
  document.getElementById("status-strip").innerHTML = [
    ["PLAN STATUS", checkpoint.status],
    ["DETAILED WINDOW", checkpoint.detailed_days_remaining == null ? "—" : `${checkpoint.detailed_days_remaining} days`],
    ["PERSONALIZATION", `${state.personalization.feedback_records}/${state.personalization.required_feedback_records} feedback records`],
  ].map(([name, value]) => `<div class="status-cell"><span>${name}</span><b>${esc(value)}</b></div>`).join("");
  renderPlan(); renderReports(); renderSettings(); renderRaces(); renderFacts();
}

function renderPlan() {
  const target = document.getElementById("active-plan"); const plan = state.active_plan;
  if (!plan) {
    target.innerHTML = '<p class="empty">No active plan. Create one when the planning data is ready.</p>';
    return;
  }
  const upcoming = plan.sessions.filter(session => session.scheduled_date >= state.as_of_date).slice(0, 3);
  target.innerHTML = `<p class="notice">Plan ${plan.id} · detailed through ${plan.detailed_end_date}</p>` + (upcoming.length ? upcoming.map(session => `<article class="plan-session"><span class="plan-date">${esc(session.scheduled_date)} · ${sport(session.sport_type)}</span><b>${esc(session.purpose)}</b><span>${km(session.distance_meters)} · ${hours(session.duration_seconds)} · ${esc(session.target_display)}</span><span>${outcome(session.feedback_outcome)}</span></article>`).join("") : '<p class="empty">No detailed sessions remain.</p>');
}

function renderReports() {
  const target = document.getElementById("reports");
  const reports = [
    ["dashboard", "Dashboard", "Training and recovery charts"],
    ["plan", "Active plan", "The complete session structure"],
    ["weekly_review", "Weekly review", "Latest AI review"],
  ];
  target.innerHTML = reports.map(([key, title, description]) => {
    const report = state.reports[key];
    if (report.available) return `<article class="report-link"><a href="${esc(report.path)}">${esc(title)} <span>↗</span></a><p>${esc(description)}</p></article>`;
    return `<article class="report-link is-unavailable"><b>${esc(title)}</b><p>${esc(report.unavailable_message)}</p></article>`;
  }).join("");
}

function renderSettings() {
  const target = document.getElementById("settings"); const preference = state.preference;
  if (!preference) { target.innerHTML = '<p class="empty">Planning preferences are not configured.</p>'; return; }
  const days = preference.available_days.map(item => `${day(item.day)}: ${item.minutes == null ? "no time limit" : `${item.minutes} min`}`).join(" · ");
  const zones = state.ride_zones?.map(zone => `<span class="zone">Z${zone.zone} ${zone.lower_bpm}–${zone.upper_bpm}</span>`).join("") || '<span class="empty">No cycling zones</span>';
  target.innerHTML = `<div class="settings-list"><div class="setting-line"><b>${ambition(preference.coaching_ambition)}</b><span>Coaching ambition</span></div><div class="setting-line"><b>${role(preference.sport_role)}</b><span>Sport role</span></div><div class="setting-line"><b>${esc(days)}</b><span>Weekly availability</span></div><div class="setting-line"><div class="zone-list">${zones}</div><span>Cycling heart-rate zones</span></div></div>`;
}

function renderRaces() {
  const target = document.getElementById("races");
  const general = `<article class="plan-choice"><b>General plan</b><p>No race is selected as the plan goal.</p><button class="text-button" type="button" data-plan-general="true">Create a plan without a race →</button></article>`;
  const races = state.races.length
    ? `<div class="races-list">${state.races.map(race => `<article class="setting-line plan-choice"><b>${esc(race.name)} · ${esc(race.priority)}</b><span>${esc(race.race_date)} · ${sport(race.sport_type)} · taper ${esc(race.taper)}</span><button class="text-button" type="button" data-plan-race-id="${race.id}">Plan for this race →</button></article>`).join("")}</div>`
    : '<p class="empty">No upcoming races saved.</p>';
  target.innerHTML = `${general}${races}`;
}

function renderFacts() {
  const target = document.getElementById("facts-grid"); const analysis = state.analysis;
  const run = analysis.sports.find(item => item.sport_type === "run"); const ride = analysis.sports.find(item => item.sport_type === "ride");
  const cells = [["TOTAL TIME / 28 D", `${analysis.total_duration_hours.toFixed(1)} h`], ["RUNNING", `${run?.activity_count || 0} sessions · ${(run?.duration_hours || 0).toFixed(1)} h`], ["CYCLING", `${ride?.activity_count || 0} sessions · ${(ride?.duration_hours || 0).toFixed(1)} h`], ["RECOVERY DATA", analysis.recovery_coverage.map(item => `${item[0]} ${item[1]}/${item[2]}`).join(" · ")]];
  target.innerHTML = cells.map(([name, value]) => `<article class="fact"><span>${name}</span><b>${esc(value)}</b></article>`).join("");
}

async function api(path, options = {}) {
  const response = await fetch(path, {headers:{"Content-Type":"application/json", "X-Pace-CSRF":csrf, ...(options.headers || {})}, ...options});
  const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Pace could not complete the action."); return data;
}

function responseExtras(answer) {
  let html = "";
  if (answer.observations?.length) html += `<ul>${answer.observations.map(item => `<li>${esc(item)}</li>`).join("")}</ul>`;
  if (answer.uncertainties?.length) html += `<p class="notice">Uncertainties: ${esc(answer.uncertainties.join(" · "))}</p>`;
  if (answer.context_event_draft) { const draft = answer.context_event_draft; html += decisionCard("Context draft", "Pace prepared this draft. Nothing is saved without your confirmation.", [["Type",draft.event_type],["From",draft.start_date],["Until",draft.ongoing ? "ongoing" : (draft.end_date || draft.start_date)]], "Save context", "context", draft); }
  if (answer.feedback_draft) { const draft = answer.feedback_draft; html += decisionCard("Session outcome", "This is a proposal based on what you wrote, not an interpretation of Garmin data.", [["Outcome",outcome(draft.outcome)],["RPE",draft.perceived_exertion == null ? "—" : `${draft.perceived_exertion}/10`],["Reason",draft.reason_code || "—"]], "Save feedback", "feedback", draft); }
  if (answer.adjustment_draft) { const draft = answer.adjustment_draft; html += `<article class="decision-card"><h3>Plan adjustment draft</h3><p>${esc(draft.rationale)}</p><p class="notice">Shown for review. Same-day adjustments are not saved automatically; a real revision will be created in a future UI release.</p></article>`; }
  return html;
}

function commandExtras(command) {
  if (!command.confirmation) return "";
  const confirmation = command.confirmation;
  return decisionCard(
    confirmation.title,
    confirmation.body,
    confirmation.values,
    confirmation.label,
    "command",
    {action: confirmation.action},
  );
}

async function submitQuestion(question) {
  addMessage("athlete", question); document.getElementById("chat-question").value = "";
  const isCommand = question.trim().startsWith("/");
  const path = isCommand ? "/api/command" : "/api/chat";
  const payload = isCommand ? {command:question} : {question};
  try {
    const answer = await api(path, {method:"POST", body:JSON.stringify(payload)});
    addMessage("coach", answer.answer, isCommand ? commandExtras(answer) : responseExtras(answer));
  }
  catch (error) { addMessage("coach", `Could not answer: ${error.message}`); }
}

document.getElementById("chat-form").addEventListener("submit", event => { event.preventDefault(); const question = document.getElementById("chat-question").value.trim(); if (question) submitQuestion(question); });
document.querySelectorAll("[data-prompt]").forEach(button => button.addEventListener("click", () => submitQuestion(button.dataset.prompt)));
document.addEventListener("click", async event => {
  const button = event.target.closest("button"); if (!button) return;
  if (button.dataset.planGeneral === "true" || button.dataset.planRaceId) {
    const raceId = button.dataset.planGeneral === "true" ? null : Number(button.dataset.planRaceId);
    const race = state.races.find(item => item.id === raceId);
    const title = race ? `Plan for ${race.name}` : "Create a general plan";
    const body = race
      ? `The ${race.priority}-priority race becomes the only plan goal. Other saved races are ignored.`
      : "No saved race becomes a plan goal. The plan is based on your current history and preferences.";
    addMessage("coach", "Check your plan choice before it is created.", decisionCard(title, body, [["Plan goal", race ? `${race.name} · ${race.priority}` : "No race"], ["Detailed window", "14 days"]], "Create and activate plan", "plan_draft", {race_id: raceId}));
    return;
  }
  if (button.dataset.action === "dismiss") { button.closest(".decision-card").remove(); return; }
  const card = button.closest(".decision-card") || button.parentElement;
  const originalLabel = button.textContent;
  try {
    if (button.dataset.action === "context" || button.dataset.action === "feedback" || button.dataset.action === "command" || button.dataset.action === "plan_draft") {
      button.disabled = true; button.textContent = "Saving…";
      const payload = JSON.parse(button.dataset.payload);
      const path = button.dataset.action === "context"
        ? "/api/context/confirm"
        : button.dataset.action === "feedback"
          ? "/api/feedback/confirm"
          : button.dataset.action === "plan_draft"
            ? "/api/plan/draft/confirm"
            : "/api/command/confirm";
      const result = await api(path, {method:"POST", body:JSON.stringify(payload)});
      card.innerHTML = button.dataset.action === "context"
        ? "<p><b>Context saved.</b> Pace has not changed the plan.</p>"
        : button.dataset.action === "feedback"
          ? "<p><b>Feedback saved.</b> The outcome is recorded and the button has been removed.</p>"
          : button.dataset.action === "plan_draft"
            ? `<p><b>Plan ${esc(result.plan.id)} is active.</b> <a class="report-action" href="/plan">Review the plan →</a></p>`
            : `<p><b>Done.</b> ${esc(result.message)}</p>`;
      await refreshHome();
    }
  } catch (error) {
    button.disabled = false; button.textContent = originalLabel;
    card.insertAdjacentHTML("beforeend", `<p class="notice"><b>Could not save.</b> ${esc(error.message)}</p>`);
  }
});
async function refreshHome() { try { state = await api("/api/home", {method:"GET"}); renderState(); } catch (error) { addMessage("coach", `Could not refresh the facts: ${error.message}`); } }
document.getElementById("refresh-home").addEventListener("click", refreshHome);
renderState();
restoreConversation();
