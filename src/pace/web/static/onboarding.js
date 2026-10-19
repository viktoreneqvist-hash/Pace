const embeddedState = document.getElementById("pace-state");
let state = JSON.parse(embeddedState.textContent);
const csrf = document.querySelector('meta[name="pace-csrf"]').content;
const errorBox = document.getElementById("setup-error");
const stepCards = [...document.querySelectorAll("[data-setup-step]")];
const baseSteps = [
  ["welcome", "Welcome"],
  ["garmin", "Garmin"],
  ["history", "Training history"],
  ["preferences", "Preferences"],
  ["zones", "Cycling zones"],
  ["ai", "AI coach"],
  ["race", "Race goal"],
  ["plan", "Create a plan"],
];

const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[char]));

async function api(path, payload = {}) {
  const response = await fetch(path, {
    method: "POST",
    headers: {"Content-Type":"application/json", "X-Pace-CSRF":csrf},
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Pace could not complete the action.");
  return data;
}

function steps() {
  return baseSteps.filter(([id]) => id !== "zones" || state.onboarding.ride_zones_required);
}

function determineInitialStep() {
  const setup = state.onboarding;
  const hasProgress = setup.garmin_connected || setup.history_ready || setup.preferences_configured;
  if (!hasProgress) return "welcome";
  if (!setup.garmin_connected) return "garmin";
  if (!setup.history_ready) return "history";
  if (!setup.preferences_configured) return "preferences";
  if (setup.ride_zones_required && !setup.ride_zones_configured) return "zones";
  return "plan";
}

let currentStep = determineInitialStep();

function stepIsDone(id) {
  const setup = state.onboarding;
  if (id === "welcome") return currentStep !== "welcome";
  if (id === "garmin") return setup.garmin_connected;
  if (id === "history") return setup.history_ready;
  if (id === "preferences") return setup.preferences_configured;
  if (id === "zones") return !setup.ride_zones_required || setup.ride_zones_configured;
  if (id === "ai") return setup.openai_configured;
  if (id === "race") return state.races.length > 0;
  return false;
}

function requiredSetupSteps() {
  return ["garmin", "history", "preferences", ...(state.onboarding.ride_zones_required ? ["zones"] : [])];
}

function pendingRequirements() {
  const setup = state.onboarding;
  if (!setup.garmin_connected) return {label:"Connect Garmin", step:"garmin"};
  if (!setup.history_ready) return {label:"Import training history", step:"history"};
  if (!setup.preferences_configured) return {label:"Save your training preferences", step:"preferences"};
  if (setup.ride_zones_required && !setup.ride_zones_configured) return {label:"Confirm your cycling zones", step:"zones"};
  if (!setup.openai_configured) return {label:"Set up the AI coach", step:"ai"};
  return null;
}

function render() {
  const visibleSteps = steps();
  if (!visibleSteps.some(([id]) => id === currentStep)) currentStep = determineInitialStep();
  const currentIndex = visibleSteps.findIndex(([id]) => id === currentStep);
  document.getElementById("setup-step-count").textContent = `STEP ${currentIndex + 1} OF ${visibleSteps.length}`;
  document.getElementById("setup-step-label").textContent = `${visibleSteps[currentIndex][1].toUpperCase()} · LOCAL SETUP`;
  document.getElementById("setup-back").disabled = currentIndex === 0;
  stepCards.forEach(card => {
    card.hidden = card.dataset.setupStep !== currentStep;
  });

  const required = requiredSetupSteps();
  const completed = required.filter(stepIsDone).length;
  const progress = document.getElementById("setup-required-progress");
  progress.max = required.length;
  progress.value = completed;
  document.getElementById("setup-required-copy").textContent = completed === required.length
    ? "Core setup complete"
    : `${completed} of ${required.length} core steps complete`;

  document.getElementById("setup-status").innerHTML = visibleSteps.map(([id, label], index) => {
    const active = id === currentStep;
    const done = stepIsDone(id);
    const optional = (id === "ai" && !done) || (id === "race" && !done);
    const ready = id === "plan" && !pendingRequirements();
    const status = active ? "Current step" : done ? "Complete" : optional ? "Optional" : ready ? "Ready" : id === "plan" ? "Needs setup" : "Not complete";
    return `<li class="${active ? "is-current" : ""} ${done ? "is-done" : ""} ${optional ? "is-optional" : ""} ${ready ? "is-ready" : ""}"><button type="button" data-go-step="${id}" aria-current="${active ? "step" : "false"}"><span class="setup-step-number">${done ? "✓" : index + 1}</span><span class="setup-step-name">${esc(label)}</span><span class="setup-step-state">${status}</span></button></li>`;
  }).join("");

  const pending = pendingRequirements();
  const historyButton = document.getElementById("history-button");
  historyButton.disabled = !state.onboarding.garmin_connected;
  document.getElementById("history-message").textContent = state.onboarding.garmin_connected
    ? "Pace will connect to Garmin only after you start the import."
    : "Connect Garmin first to import your history.";
  const planActions = document.getElementById("setup-plan-actions");
  if (pending) {
    const reason = pending.step === "ai"
      ? "An OpenAI API key is needed to create an AI-generated plan. You can still explore your local dashboard without one."
      : `${pending.label} before a plan can be created.`;
    planActions.innerHTML = `<p class="notice">${reason}</p><div class="setup-action-row"><button class="primary" type="button" data-go-step="${pending.step}">Continue setup: ${esc(pending.label)}</button></div>`;
    return;
  }

  const choices = [
    `<button class="primary" type="button" data-draft="general">Create a general plan</button>`,
    ...state.races.map(race => `<button class="secondary" type="button" data-draft="${race.id}">Plan for ${esc(race.name)} · ${esc(race.priority)}</button>`),
  ];
  planActions.innerHTML = `<p class="notice">Choose a goal to create your first plan. Saved races are not used unless you select one here.</p><div class="plan-action-list">${choices.join("")}</div>`;
}

function goTo(step) {
  if (steps().some(([id]) => id === step)) {
    currentStep = step;
    clearError();
    render();
    const heading = document.querySelector(`[data-setup-step="${step}"] h2`);
    heading?.setAttribute("tabindex", "-1");
    heading?.focus();
    window.scrollTo({top:0, behavior:"smooth"});
  }
}

function nextAfter(step) {
  const visibleSteps = steps();
  const index = visibleSteps.findIndex(([id]) => id === step);
  if (index >= 0 && index < visibleSteps.length - 1) goTo(visibleSteps[index + 1][0]);
}

function start(button, label = "Saving…") {
  button.disabled = true;
  button.dataset.originalLabel = button.textContent;
  button.textContent = label;
}

function stop(button) {
  button.disabled = false;
  button.textContent = button.dataset.originalLabel || "Try again";
}

function showError(error, {garmin = false} = {}) {
  errorBox.textContent = error.message;
  errorBox.hidden = false;
  if (garmin && /mfa|verification|code/i.test(error.message)) {
    document.getElementById("garmin-mfa-label").hidden = false;
    document.getElementById("garmin-mfa-hint").hidden = false;
  }
}

function clearError() {
  errorBox.hidden = true;
  errorBox.textContent = "";
}

function update(nextState) {
  state = nextState.state || nextState;
  render();
}

async function streamHistory(button) {
  start(button, "Starting import…");
  const progress = document.getElementById("history-progress");
  const message = document.getElementById("history-message");
  progress.hidden = false;
  progress.value = 0;
  message.textContent = "Connecting to Garmin…";
  const response = await fetch("/api/setup/history/stream", {
    method:"POST",
    headers:{"Content-Type":"application/json","X-Pace-CSRF":csrf},
    body:JSON.stringify({days:80}),
  });
  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.detail || "The history import could not start.");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let complete = false;
  const slow = window.setTimeout(() => {
    message.textContent = "Garmin is still processing the current batch. You can leave this page open.";
  }, 45_000);
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, {stream:true});
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";
      for (const part of parts) {
        const event = part.match(/^event: (.+)$/m)?.[1];
        const raw = part.match(/^data: (.+)$/m)?.[1];
        if (!event || !raw) continue;
        const payload = JSON.parse(raw);
        if (event === "progress") {
          progress.max = payload.total_batches;
          progress.value = payload.completed_batches;
          message.textContent = payload.phase === "started"
            ? `Importing batch ${payload.completed_batches + 1} of ${payload.total_batches}…`
            : `Imported batch ${payload.completed_batches} of ${payload.total_batches}.`;
        }
        if (event === "error") throw new Error(payload.message);
        if (event === "completed") {
          update(payload.state);
          progress.value = progress.max;
          message.textContent = "History imported and saved on this computer.";
          button.disabled = false;
          button.textContent = "Import complete";
          complete = true;
        }
      }
    }
  } finally {
    window.clearTimeout(slow);
  }
  if (!complete) throw new Error("The connection closed before the import finished. Completed batches were saved; try again to continue.");
  nextAfter("history");
}

document.getElementById("setup-back").addEventListener("click", () => {
  const visibleSteps = steps();
  const index = visibleSteps.findIndex(([id]) => id === currentStep);
  if (index > 0) goTo(visibleSteps[index - 1][0]);
});
document.addEventListener("click", event => {
  const button = event.target.closest("[data-go-step]");
  if (button) goTo(button.dataset.goStep);
});

document.getElementById("setup-openai").addEventListener("submit", async event => {
  event.preventDefault();
  clearError();
  const button = event.currentTarget.querySelector('button[type="submit"]');
  start(button);
  try {
    update(await api("/api/setup/openai", {api_key:new FormData(event.currentTarget).get("api_key")}));
    event.currentTarget.reset();
    document.getElementById("ai-saved-message").hidden = false;
    nextAfter("ai");
  } catch (error) {
    showError(error);
    stop(button);
  }
});

document.getElementById("setup-garmin").addEventListener("submit", async event => {
  event.preventDefault();
  clearError();
  const button = event.currentTarget.querySelector('button[type="submit"]');
  start(button, "Connecting…");
  const form = new FormData(event.currentTarget);
  try {
    update(await api("/api/setup/garmin", {
      email:form.get("email"),
      password:form.get("password"),
      mfa_code:form.get("mfa_code") || null,
    }));
    event.currentTarget.reset();
    document.getElementById("garmin-mfa-label").hidden = true;
    document.getElementById("garmin-mfa-hint").hidden = true;
    nextAfter("garmin");
  } catch (error) {
    showError(error, {garmin:true});
    stop(button);
  }
});

document.getElementById("setup-preferences").addEventListener("submit", async event => {
  event.preventDefault();
  clearError();
  const button = event.currentTarget.querySelector('button[type="submit"]');
  start(button);
  const form = new FormData(event.currentTarget);
  const available_days = [...event.currentTarget.querySelectorAll('input[name="day"]:checked')].map(item => item.value);
  try {
    update(await api("/api/setup/preferences", {
      sport_role:form.get("sport_role"),
      coaching_ambition:form.get("coaching_ambition"),
      available_days,
    }));
    nextAfter("preferences");
  } catch (error) {
    showError(error);
    stop(button);
  }
});

document.getElementById("setup-zones").addEventListener("submit", async event => {
  event.preventDefault();
  clearError();
  const button = event.currentTarget.querySelector('button[type="submit"]');
  start(button);
  const form = new FormData(event.currentTarget);
  const zones = [1,2,3,4,5].map(number => `${number}:${String(form.get(`zone_${number}`) || "").trim()}`);
  try {
    update(await api("/api/setup/zones", {zones}));
    nextAfter("zones");
  } catch (error) {
    showError(error);
    stop(button);
  }
});

document.getElementById("setup-race").addEventListener("submit", async event => {
  event.preventDefault();
  clearError();
  const form = new FormData(event.currentTarget);
  if (!form.get("name") && !form.get("race_date") && !form.get("distance_km")) {
    nextAfter("race");
    return;
  }
  const button = event.currentTarget.querySelector('button[type="submit"]');
  start(button);
  try {
    update(await api("/api/setup/races", Object.fromEntries(form)));
    event.currentTarget.reset();
    nextAfter("race");
  } catch (error) {
    showError(error);
    stop(button);
  }
});

document.getElementById("history-button").addEventListener("click", async event => {
  clearError();
  const button = event.currentTarget;
  try {
    await streamHistory(button);
  } catch (error) {
    showError(error);
    stop(button);
  }
});

document.addEventListener("click", async event => {
  const button = event.target.closest("[data-draft]");
  if (!button) return;
  clearError();
  start(button, "Creating your plan…");
  const raw = button.dataset.draft;
  try {
    const result = await api("/api/plan/draft/confirm", {race_id:raw === "general" ? null : Number(raw)});
    window.location.assign(`/plan?draft=${result.plan.id}`);
  } catch (error) {
    showError(error);
    stop(button);
  }
});

render();
