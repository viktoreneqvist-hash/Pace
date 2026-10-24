# Pace prototype roadmap

Constraints: no Lovable Cloud, Supabase, auth, telemetry, server functions,
external fonts, or external API calls. All data synthetic and behind
MockPaceClient. In-memory mutation state only; refresh may reset it.

## Step 1 — shared foundation + Today / Coach (done, approved)
- [x] Design tokens in src/styles.css
- [x] Persistent app shell with navigation, local-only marker, max-width frame
- [x] Typed PaceClient + MockPaceClient (HttpPaceClient boundary documented, not implemented)
- [x] Reusable states: loading, empty, stale, partial, failed, completed, pending, unknown
- [x] Today / Coach: session, rationale, facts, sync state machine, coach conversation with confirmable action cards
- [x] Placeholder routes for every nav item

## Step 2 — Plan (done, approved)
- [x] Goal, priority, race date, desired time, taper policy, detailed-window dates
- [x] Compact week-by-week block timeline with race marker
- [x] Session cards: prescribed / observed Garmin / athlete feedback / coach assessment
- [x] Required examples: easy run, steady ride, intervals, completed with RPE, limited, no feedback
- [x] Revision-not-due and revision-due states; generation gated to revision-due
- [x] Busy, validation-failure, retry, success; plan replaced only after validation passes
- [x] Quiet plan-history disclosure

## Step 3 — Dashboard (done)
- [x] Separate run/ride training, HRV, RHR, sleep, reported RPE, coverage, last sync
- [x] 28/84-day windows, missing data as gaps, no single combined score
- [x] Charts: axes, units, dates, legend, pointer tooltip, keyboard readout, raw-value table

## Step 4 — Weekly Review (done)
- [x] Absent, running, failed, retry, saved; never regenerates on open
- [x] Dated immutable snapshot; separate Pace facts, Garmin facts, judgment, uncertainty, knowledge
- [x] Earlier snapshots list

## Step 5 — Races (done)
- [x] Future races, A/B/C priority, taper policy, desired time as ambition
- [x] Registration validation; registration never changes the plan target
- [x] Explicit target selection; cancellation with confirmation; immutable history

## Step 6 — Settings (done)
- [x] Five sport roles, three ambition levels, availability and time caps
- [x] Five cycling heart-rate zones with validation
- [x] Connection status, reconnect failure/retry, synthetic-only credential field
- [x] Explicit 7-day and 80-day sync with progress and outcomes

## Step 7 — Onboarding (done)
- [x] Resumable steps with complete, in-progress, blocked, optional, to-do states
- [x] Confirmation, busy, failure, retry; blocked steps unlock when prerequisites finish

## Step 8 — Session detail and feedback (done)
- [x] Prescribed / Garmin-observed / feedback / coach assessment kept separate
- [x] Completed, completed with limitations, skipped; optional RPE, reason, private note
- [x] Explicit share-with-AI control, confirmation step, duplicate-submit prevention
- [x] Local validation failure path (reason required) before anything is saved

## Verification
- [x] tsgo type check clean
- [x] eslint 0 errors (6 pre-existing template Fast Refresh warnings)
- [x] production build succeeds
- [x] Playwright: all 8 routes at 1280 and 390 px, no horizontal overflow, no console errors
- [x] Playwright flows: weekly review fail→retry→saved, race validation→saved, zone validation
      failure, onboarding 80-day sync fail→retry→complete, feedback validation→saved, chart
      keyboard readout

## Not done (out of prototype scope)
- [ ] HttpPaceClient against same-origin /api/v1/* (boundary documented only)
