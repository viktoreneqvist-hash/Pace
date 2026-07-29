const embeddedState = document.getElementById("pace-state");
let state = JSON.parse(embeddedState.textContent);
const csrf = document.querySelector('meta[name="pace-csrf"]').content;
const errorBox = document.getElementById("setup-error");

const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[char]));

async function api(path, payload = {}) {
  const response = await fetch(path, {
    method: "POST",
    headers: {"Content-Type":"application/json", "X-Pace-CSRF":csrf},
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Pace kunde inte slutföra åtgärden.");
  return data;
}

function pendingRequirements() {
  const setup = state.onboarding;
  const pending = [];
  if (!setup.openai_configured) pending.push("AI-nyckel");
  if (!setup.garmin_connected) pending.push("Garmin");
  if (!setup.preferences_configured) pending.push("träningsram");
  if (setup.ride_zones_required && !setup.ride_zones_configured) pending.push("cykelpulszoner");
  if (!setup.history_ready) pending.push("Garmin-historik");
  return pending;
}

function render() {
  const setup = state.onboarding;
  const rows = [
    ["AI-nyckel", setup.openai_configured], ["Garmin", setup.garmin_connected],
    ["Träningsram", setup.preferences_configured],
    ["Cykelpulszoner", !setup.ride_zones_required || setup.ride_zones_configured],
    ["Planeringsunderlag", setup.history_ready],
  ];
  document.getElementById("setup-status").innerHTML = rows.map(([label, done]) => `<span class="setup-state ${done ? "done" : ""}"><b>${done ? "KLAR" : "ÅTERSTÅR"}</b>${esc(label)}</span>`).join("");
  document.getElementById("setup-openai").classList.toggle("is-complete", setup.openai_configured);
  document.getElementById("setup-garmin").classList.toggle("is-complete", setup.garmin_connected);
  document.getElementById("setup-preferences").classList.toggle("is-complete", setup.preferences_configured);
  document.getElementById("setup-zones").hidden = !setup.ride_zones_required;
  document.getElementById("setup-zones").classList.toggle("is-complete", setup.ride_zones_configured);
  document.getElementById("setup-history").classList.toggle("is-complete", setup.history_ready);
  const pending = pendingRequirements();
  const planActions = document.getElementById("setup-plan-actions");
  if (pending.length) {
    planActions.innerHTML = `<p class="notice">Återstår innan Pace kan planera: ${esc(pending.join(", "))}.</p>`;
    return;
  }
  const choices = [
    `<button class="primary" type="button" data-draft="general">Skapa generell plan</button>`,
    ...state.races.map(race => `<button class="secondary" type="button" data-draft="${race.id}">Planera mot ${esc(race.name)} · ${esc(race.priority)}</button>`),
  ];
  planActions.innerHTML = `<p class="notice">Välj exakt ett planmål. Sparade lopp påverkar ingenting förrän du väljer dem här.</p><div class="plan-action-list">${choices.join("")}</div>`;
}

function start(button) { button.disabled = true; button.dataset.originalLabel = button.textContent; button.textContent = "Sparar…"; }
function stop(button) { button.disabled = false; button.textContent = button.dataset.originalLabel || "Försök igen"; }
function showError(error) { errorBox.textContent = error.message; errorBox.hidden = false; }
function clearError() { errorBox.hidden = true; errorBox.textContent = ""; }
function update(nextState) { state = nextState.state || nextState; render(); }

document.getElementById("setup-openai").addEventListener("submit", async event => {
  event.preventDefault(); clearError(); const button = event.currentTarget.querySelector("button"); start(button);
  try { update(await api("/api/setup/openai", {api_key: new FormData(event.currentTarget).get("api_key")})); event.currentTarget.reset(); }
  catch (error) { showError(error); stop(button); }
});
document.getElementById("setup-garmin").addEventListener("submit", async event => {
  event.preventDefault(); clearError(); const button = event.currentTarget.querySelector("button"); start(button); const form = new FormData(event.currentTarget);
  try { update(await api("/api/setup/garmin", {email:form.get("email"), password:form.get("password"), mfa_code:form.get("mfa_code") || null})); event.currentTarget.reset(); }
  catch (error) { showError(error); stop(button); }
});
document.getElementById("setup-preferences").addEventListener("submit", async event => {
  event.preventDefault(); clearError(); const button = event.currentTarget.querySelector("button"); start(button); const form = new FormData(event.currentTarget);
  const available_days = [...event.currentTarget.querySelectorAll('input[name="day"]:checked')].map(item => item.value);
  try { update(await api("/api/setup/preferences", {sport_role:form.get("sport_role"), coaching_ambition:form.get("coaching_ambition"), available_days})); }
  catch (error) { showError(error); stop(button); }
});
document.getElementById("setup-zones").addEventListener("submit", async event => {
  event.preventDefault(); clearError(); const button = event.currentTarget.querySelector("button"); start(button); const form = new FormData(event.currentTarget);
  const zones = [1,2,3,4,5].map(number => `${number}:${String(form.get(`zone_${number}`) || "").trim()}`);
  try { update(await api("/api/setup/zones", {zones})); }
  catch (error) { showError(error); stop(button); }
});
document.getElementById("setup-race").addEventListener("submit", async event => {
  event.preventDefault(); clearError(); const form = new FormData(event.currentTarget);
  if (!form.get("name") && !form.get("race_date") && !form.get("distance_km")) return;
  const button = event.currentTarget.querySelector("button"); start(button);
  try { update(await api("/api/setup/races", Object.fromEntries(form))); event.currentTarget.reset(); }
  catch (error) { showError(error); stop(button); }
});
document.getElementById("history-button").addEventListener("click", async event => {
  clearError(); const button = event.currentTarget; start(button); button.textContent = "Hämtar fyra säkra batcher…";
  try { update(await api("/api/setup/history/confirm", {days:80})); button.textContent = "Historik hämtad"; }
  catch (error) { showError(error); stop(button); }
});
document.addEventListener("click", async event => {
  const button = event.target.closest("[data-draft]"); if (!button) return;
  clearError(); start(button); const raw = button.dataset.draft;
  try {
    const result = await api("/api/plan/draft/confirm", {race_id: raw === "general" ? null : Number(raw)});
    window.location.assign(`/plan?draft=${result.plan.id}`);
  } catch (error) { showError(error); stop(button); }
});
render();
