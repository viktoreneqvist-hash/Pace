# Pace project knowledge

## Product

Pace is a local-first AI endurance coach for one athlete. It combines Garmin
running, cycling, sleep, HRV, and resting-heart-rate data with athlete context,
explicit session feedback, races, preferences, reviewed training knowledge,
and bounded AI coaching. It creates a long block toward a goal but details only
the next 7–14 days. It is an honest coach, not a motivational wellness app.

The product language is English. The coach voice is direct, factual, concise,
and unsentimental. It separates observed facts, coaching judgment, and
uncertainty. It does not flatter, diagnose, or hide missing evidence.

## Existing system of record

The production core already exists in Python:

- FastAPI loopback application, available only on `127.0.0.1`;
- SQLite with versioned Alembic migrations;
- Garmin synchronization and locally stored owner-only tokens;
- deterministic metrics, continuity evidence, recovery baselines, and rules;
- structured context events and explicit workout feedback;
- validated, immutable training-plan versions and structured workout steps;
- stateless OpenAI calls over selected normalized Pace facts;
- CSRF protection, Host validation, and restrictive browser security headers.

The React interface must call a same-origin local Pace API. It must never open
SQLite, call Garmin, call OpenAI, calculate coaching facts, or persist canonical
training state itself. Python remains responsible for validation and writes.

## Prototype mode

Lovable cannot access a user's localhost. Build the first prototype entirely
with synthetic fixtures and a typed data adapter that can later be replaced by
same-origin `/api/v1/*` calls. Do not enable Lovable Cloud, Supabase,
authentication, telemetry, remote storage, or external API integrations.

Never include real athlete data, Garmin tokens, OpenAI keys, passwords, private
notes, raw provider payloads, GPS routes, or per-second streams.

## Users and normal workflow

The main user is a serious amateur runner/cyclist who wants decisions grounded
in actual history rather than self-reported volume. After launching Pace, the
user should not need a terminal.

Normal workflow:

1. Onboard locally: OpenAI key, Garmin connection, sport role, ambition,
   availability, optional cycling zones, 80-day history sync, races, first plan.
2. Open Today/Coach and see today's session, current facts, warnings, and chat.
3. Sync Garmin explicitly and watch progress.
4. Record context or workout feedback through reviewed confirmation cards.
5. Inspect Dashboard, Plan, Weekly Review, Races, and Settings.
6. Request the next 14 detailed days only when the current window is due.

## Athlete-controlled settings

- Sport role: run only, run primary, balanced, ride primary, ride only.
- Coaching ambition: cautious, balanced, ambitious.
- Available weekdays and optional time caps.
- Five confirmed Garmin cycling heart-rate zones.
- Races with name, sport, date, distance, A/B/C priority, optional desired
  time, and taper policy.

Race priority means: A is the primary goal with full taper, B is a hard
secondary race with partial taper, and C is a hard training event without a
race taper. The athlete explicitly chooses one race or a general plan whenever
a plan is created.

## Required product areas

### Today / Coach

Today's planned session, concise recovery and data-quality facts, recent coach
conversation, safe slash commands, and confirmable action cards. Conversation
history is bounded and disappears when the local server stops. Model output
never writes directly.

### Dashboard

Information-dense training and recovery views. Show running and cycling
separately. Charts need visible dates, axes, units, legends, and hover/focus
tooltips with raw values. Include 28/84-day context and data-quality coverage.

### Plan

Active goal, block timeline, next 14 detailed days, race markers, and structured
session cards. A workout may be one steady block or multiple warm-up, interval,
recovery, and cooldown steps. Do not add warm-up/cooldown automatically. Show
purpose, duration/distance, target, outcome, and feedback. Old accepted plans
are immutable history.

### Weekly Review

One explicit dated AI snapshot. Clearly separate observations, coaching
assessment, actions, uncertainties, and knowledge support. Opening the page
must not rerun AI.

### Races and Settings

Add/edit/cancel eligible future races. Edit sport role, ambition, availability,
zones, connections, and start 7- or 80-day Garmin syncs with visible progress.

### Onboarding

A resumable guided sequence for every prerequisite. Explain local privacy and
show what is complete, in progress, blocked, or optional. The first plan is
created only after explicit target selection and complete Python validation.

## Visual direction

Create an editorial sport-science product, not a generic AI dashboard. Use a
warm off-white canvas, ink-black text, restrained forest green, one energetic
accent, squared or lightly rounded geometry, strong grid lines, compact labels,
and dense but legible data. Avoid dark mode as the default, gradients, glass,
glows, pill overload, huge empty hero areas, excessive rounding, and giant
numbers that crowd out the chart.

Use one persistent navigation shell across every page. Center content in a
responsive maximum-width frame. Desktop should feel like a serious training
journal and lab report; mobile should preserve hierarchy without horizontal
overflow. Use accessible semantic HTML, keyboard focus, contrast, and chart
alternatives.

## Non-negotiable trust boundaries

- Local-only and single-athlete in v0.1; no accounts or cloud deployment.
- Same-origin browser/API boundary; no direct database access.
- No secrets or raw Garmin data in browser-delivered JavaScript.
- No automatic sync, AI call, plan replacement, or retrospective rewrite.
- Every persistent mutation is explicit, CSRF-protected, validated by Python,
  and returns a visible completed or failed state.
- Missing data is unknown, never zero.
- Run and ride are the only sports included in coaching calculations.
- General plan mode must not silently target a stored race.
- New UI labels are English; old stored Swedish content may remain historical.
