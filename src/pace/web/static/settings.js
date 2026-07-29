const embeddedState = document.getElementById("pace-state");
let state = JSON.parse(embeddedState.textContent);
const csrf = document.querySelector('meta[name="pace-csrf"]').content;
const errorBox = document.getElementById("settings-error");
const savedBox = document.getElementById("settings-saved");
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[char]));
const weekdayLabels = {mon:"Mån",tue:"Tis",wed:"Ons",thu:"Tor",fri:"Fre",sat:"Lör",sun:"Sön"};
const roleLabels = {run_only:["Endast löpning","Inga cykelpass."],run_primary:["Löpning primär","Löpning i fokus, cykel kan stötta."],balanced:["Balanserad","Coachen väljer sport utifrån fakta."],ride_primary:["Cykling primär","Cykling i fokus, löpning kan stötta."],ride_only:["Endast cykling","Inga löppass."]};
const ambitionLabels = {cautious:"Försiktig",balanced:"Balanserad",ambitious:"Offensiv"};

async function api(path, method = "POST", payload) {
  const response = await fetch(path, {method, headers:{"Content-Type":"application/json","X-Pace-CSRF":csrf}, body: payload === undefined ? undefined : JSON.stringify(payload)});
  const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Pace kunde inte slutföra ändringen."); return data;
}
function showError(error) { errorBox.textContent = error.message; errorBox.hidden = false; }
function clearNotice() { errorBox.hidden = true; savedBox.hidden = true; }
function saved(message) { savedBox.textContent = message; savedBox.hidden = false; }
function busy(button, text) { button.disabled = true; button.dataset.label = button.textContent; button.textContent = text; }
function idle(button) { button.disabled = false; button.textContent = button.dataset.label || "Försök igen"; }
function update(response) { state = response.state || response; render(); }

async function streamHistory(days, button) {
  busy(button, "Startar Garmin-synk…");
  const response = await fetch("/api/setup/history/stream", {method:"POST",headers:{"Content-Type":"application/json","X-Pace-CSRF":csrf},body:JSON.stringify({days})});
  if (!response.ok) { const data = await response.json(); throw new Error(data.detail || "Historikimporten kunde inte starta."); }
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ""; let complete = false;
  const slow = window.setTimeout(() => saved("Garmin arbetar fortfarande med den aktuella batchen. Redan klara batcher är sparade."), 45_000);
  try {
    while (true) {
      const chunk = await reader.read(); if (chunk.done) break;
      buffer += decoder.decode(chunk.value, {stream:true});
      const parts = buffer.split("\n\n"); buffer = parts.pop() || "";
      for (const part of parts) {
        const event = part.match(/^event: (.+)$/m)?.[1]; const raw = part.match(/^data: (.+)$/m)?.[1]; if (!event || !raw) continue;
        const payload = JSON.parse(raw);
        if (event === "progress") {
          const range = `${payload.start_date} – ${payload.end_date}`;
          saved(payload.phase === "started" ? `Batch ${payload.completed_batches + 1} av ${payload.total_batches} körs: ${range}.` : `Batch ${payload.completed_batches} av ${payload.total_batches} klar: ${range}.`);
        }
        if (event === "error") throw new Error(payload.message);
        if (event === "completed") { update(payload.state); saved(payload.message); complete = true; }
      }
    }
  } finally { window.clearTimeout(slow); }
  if (!complete) throw new Error("Synkanslutningen avslutades innan Pace fick ett slutresultat. Redan färdiga batcher är sparade.");
  button.disabled = false; button.textContent = "Synkad";
}

function render() {
  const pref = state.preference || {sport_role:"balanced",coaching_ambition:"balanced",available_days:[]};
  document.getElementById("settings-role-choices").innerHTML = Object.entries(roleLabels).map(([value,[title,text]]) => `<label><input type="radio" name="sport_role" value="${value}" ${pref.sport_role === value ? "checked" : ""}><b>${title}</b><span>${text}</span></label>`).join("");
  document.getElementById("settings-ambition-choices").innerHTML = Object.entries(ambitionLabels).map(([value,label]) => `<label><input type="radio" name="coaching_ambition" value="${value}" ${pref.coaching_ambition === value ? "checked" : ""}> ${label}</label>`).join("");
  const available = new Set(pref.available_days.map(item => item.day));
  document.getElementById("settings-days").innerHTML = Object.entries(weekdayLabels).map(([value,label]) => `<label><input type="checkbox" name="day" value="${value}:any" ${available.has(value) ? "checked" : ""}> ${label}</label>`).join("");
  const zones = state.ride_zones || [];
  document.getElementById("settings-zones").innerHTML = [1,2,3,4,5].map(number => { const zone = zones.find(item => item.zone === number); const value = zone ? `${zone.lower_bpm}-${zone.upper_bpm}` : ""; return `<label>Z${number}<input name="zone_${number}" value="${esc(value)}" placeholder="99-118" inputmode="numeric"></label>`; }).join("");
  document.getElementById("settings-zones-card").hidden = pref.sport_role === "run_only";
  document.getElementById("settings-races").innerHTML = state.races.length ? state.races.map(race => `<form class="race-edit" data-race-id="${race.id}"><div class="race-edit-heading"><b>${esc(race.name)}</b><span>${esc(race.priority)} · taper ${esc(race.taper)}</span></div><div class="race-inputs"><label>Namn<input name="name" value="${esc(race.name)}" required></label><label>Datum<input name="race_date" type="date" value="${esc(race.race_date)}" required></label><label>Distans (km)<input name="distance_km" type="number" step="0.1" value="${esc(race.distance_km)}" required></label><label>Sport<select name="sport_type"><option value="run" ${race.sport_type === "run" ? "selected" : ""}>Löpning</option><option value="ride" ${race.sport_type === "ride" ? "selected" : ""}>Cykling</option></select></label><label>Prioritet<select name="priority">${["A","B","C"].map(value => `<option value="${value}" ${race.priority === value ? "selected" : ""}>${value}</option>`).join("")}</select></label></div><div class="plan-action-list"><button class="text-button" type="submit">Uppdatera lopp</button><button class="text-button danger" data-remove-race="${race.id}" type="button">Ta bort lopp</button></div></form>`).join("") : '<p class="empty">Inga framtida lopp är sparade.</p>';
}

document.getElementById("settings-preferences").addEventListener("submit", async event => { event.preventDefault(); clearNotice(); const button = event.currentTarget.querySelector("button"); busy(button,"Sparar…"); const form = new FormData(event.currentTarget); const available_days = [...event.currentTarget.querySelectorAll('input[name="day"]:checked')].map(item => item.value); try { update(await api("/api/setup/preferences","POST",{sport_role:form.get("sport_role"),coaching_ambition:form.get("coaching_ambition"),available_days})); saved("Träningsram sparad. Nästa utkast använder den."); } catch (error) { showError(error); idle(button); } });
document.getElementById("settings-zones-form").addEventListener("submit", async event => { event.preventDefault(); clearNotice(); const button = event.currentTarget.querySelector("button"); busy(button,"Sparar…"); const form = new FormData(event.currentTarget); try { update(await api("/api/setup/zones","POST",{zones:[1,2,3,4,5].map(number => `${number}:${String(form.get(`zone_${number}`) || "").trim()}`)})); saved("Cykelpulszoner sparade."); } catch (error) { showError(error); idle(button); } });
document.getElementById("settings-race-add").addEventListener("submit", async event => { event.preventDefault(); clearNotice(); const button = event.currentTarget.querySelector("button"); busy(button,"Sparar…"); try { update(await api("/api/setup/races","POST",Object.fromEntries(new FormData(event.currentTarget)))); event.currentTarget.reset(); saved("Lopp sparat. Det blir planmål först när du väljer det inför ett nytt utkast."); } catch (error) { showError(error); idle(button); } });
document.getElementById("settings-openai").addEventListener("submit", async event => { event.preventDefault(); clearNotice(); const button = event.currentTarget.querySelector("button"); busy(button,"Sparar…"); try { update(await api("/api/setup/openai","POST",{api_key:new FormData(event.currentTarget).get("api_key")})); event.currentTarget.reset(); saved("AI-nyckeln är ersatt lokalt."); } catch (error) { showError(error); idle(button); } });
document.getElementById("settings-garmin").addEventListener("submit", async event => { event.preventDefault(); clearNotice(); const button = event.currentTarget.querySelector("button"); busy(button,"Ansluter…"); const form = new FormData(event.currentTarget); try { update(await api("/api/setup/garmin","POST",{email:form.get("email"),password:form.get("password"),mfa_code:form.get("mfa_code") || null})); event.currentTarget.reset(); saved("Garmin-sessionen är uppdaterad lokalt."); } catch (error) { showError(error); idle(button); } });
document.addEventListener("click", async event => { const sync = event.target.closest("[data-sync-days]"); const remove = event.target.closest("[data-remove-race]"); if (sync) { clearNotice(); try { await streamHistory(Number(sync.dataset.syncDays), sync); } catch (error) { showError(error); idle(sync); } } if (remove) { clearNotice(); if (!window.confirm("Ta bort detta lopp? Lopp som redan används av en plan eller ett resultat skyddas av Pace.")) return; busy(remove,"Tar bort…"); try { update(await api(`/api/settings/races/${remove.dataset.removeRace}`,"DELETE")); saved("Loppet är borttaget."); } catch (error) { showError(error); idle(remove); } } });
document.addEventListener("submit", async event => { const form = event.target.closest(".race-edit"); if (!form) return; event.preventDefault(); clearNotice(); const button = form.querySelector('button[type="submit"]'); busy(button,"Sparar…"); try { update(await api(`/api/settings/races/${form.dataset.raceId}`,"PUT",Object.fromEntries(new FormData(form)))); saved("Loppet är uppdaterat."); } catch (error) { showError(error); idle(button); } });
render();
