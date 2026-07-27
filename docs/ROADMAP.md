# Pace — Development Roadmap

## Goal

Build a private, local-first endurance coaching system in this order:

```text
Garmin data
    -> local database
    -> deterministic facts
    -> context memory
    -> athlete state
    -> transparent rules
    -> AI later
```

The roadmap is deliberately sequential. A later layer must consume stable,
tested outputs from the layer before it.

## Completed foundation

### Batch A — Project reset

- [x] Preserve the final Strava version in `archive/strava-v0.1.0`
- [x] Preserve tag `strava-final-v0.1.0`
- [x] Move active development to package `pace`
- [x] Make Garmin the only v1 provider
- [x] Align project documentation with the local-first architecture

### Batch B — Local database

- [x] SQLite engine and SQLAlchemy session management
- [x] Alembic migration and `pace db init`
- [x] `activities`, `daily_metrics`, `context_events`, and `sync_runs`
- [x] Unique activity and daily-metric identities
- [x] Isolated migrated test database
- [x] Git-ignore database files and SQLite sidecars
- [x] Owner-only Pace database directory and file permissions

### Batch C — Garmin ingestion

- [x] Hidden password and MFA input
- [x] Reusable owner-only local token storage
- [x] Small Pace-owned Garmin client boundary
- [x] Activity and daily recovery retrieval
- [x] Realistic top-level and nested activity normalization
- [x] Strict `run`, `ride`, or `other` sport contract
- [x] Atomic activity import and idempotent upserts
- [x] Endpoint-scoped recovery merging
- [x] Partial-result handling for unavailable recovery signals
- [x] Explicit stop behavior for authentication and rate limits
- [x] Auditable `sync_runs` with actual inserted and changed counts
- [x] Maximum seven-day batches and historical `--end-date`

### Batch D — Deterministic facts

- [x] Two adjacent seven-day training windows
- [x] Strict exclusion of every sport except `run` and `ride`
- [x] Stockholm-local calendar windows over UTC activity instants
- [x] Explicit missing-distance results instead of invented zeros
- [x] 28-day HRV, resting-heart-rate, and sleep baselines
- [x] Seven-day recent recovery averages
- [x] Observed and expected baseline data-point counts
- [x] Deterministic `pace metrics summary` output
- [x] No thresholds, readiness labels, or coaching advice in metrics

## Current quality gate

Before beginning the next batch:

- [x] Ruff passes
- [x] Full test suite passes
- [x] Alembic has one head, upgrades a blank database, and reports no drift
- [x] CLI help and database initialization pass against isolated local state
- [x] Independent review finds no unresolved P0 or P1 technical risk

## Batch E — Context memory

### Goal

Store facts that Garmin cannot observe and retrieve only the events relevant to
a date or analysis window.

### Small first slice

- [x] Define the supported event contract from concrete use cases
- [x] Add `pace note add` with explicit date, type, note, optional end date,
  and explicit `--ongoing`
- [x] Add `pace note list` with overlap date filtering
- [x] Query active or overlapping events through the repository
- [x] Add validation and tests for date overlap and missing required input

### Constraints

- Chat history is not application memory.
- Context notes remain local and are never included wholesale in AI input.
- Context does not reinterpret metrics inside the metrics layer.
- Do not add embeddings, a vector database, an LLM, athlete state, or coaching
  rules in this batch.
- Injury, goal, schedule, and training-policy semantics that affect coaching
  require explicit owner decisions before later rule work.

### Success criteria

Pace can store and retrieve structured athlete context by date without changing
the deterministic Garmin facts. This first slice supports `illness`, `pain`,
`travel`, `alcohol`, `poor_sleep`, `work_stress`, and `schedule_constraint`.

An ordinary note closes on its start date unless an explicit end date is given.
Only `--ongoing` creates an active, open-ended event.

## Later batches

### Batch F — Athlete state

Build a compact, structured snapshot from deterministic facts and relevant
context. Define freshness and confidence explicitly. Do not infer goal
priority, sport allocation, injury limits, intensity distribution, or training
progression without owner decisions.

- [x] Add a dynamic, read-only athlete state with no new database table
- [x] Include existing deterministic metrics unchanged
- [x] Include only context overlapping the current seven-day window, including
  explicitly ongoing events
- [x] Include the latest completed sync audit record and explicit recovery
  coverage counts as data quality
- [x] Add `pace state show` JSON output with optional `--end-date`
- [x] Keep state free from readiness labels, physiology claims, and coaching
  recommendations

### Batch G — Rule engine

Add transparent, tested rules over athlete state. Rules produce structured
interpretations, not hidden calculations or medical diagnoses.

- [x] Add a read-only Python rule service and structured JSON output
- [x] Require 14 observed HRV baseline days before HRV interpretation
- [x] Require two consecutive calendar days below the current HRV baseline
- [x] Select only `poor_sleep`, `alcohol`, `travel`, `work_stress`, and
  `illness` as first-slice HRV context
- [x] Use the signal date and two preceding calendar days as the context window
- [x] Expose evidence and limitations without advice, prose, or diagnosis
- [x] Add `pace rules evaluate` with optional `--end-date`

### Batch H — Explanation layer

Turn structured facts and rule output into concise explanations, initially with
deterministic templates.

- [x] Add a read-only deterministic explanation service and `pace explain`
- [x] Explain insufficient HRV data without a readiness or health claim
- [x] Explain the approved two-day HRV pattern and selected context without
  claiming causality
- [x] Offer one neutral context check-in only when the HRV signal exists and
  selected context is absent
- [x] Never store a response automatically; context remains an explicit note
- [x] Keep rule JSON available separately through `pace rules evaluate`

### Recovery expansion — before Batch I

Extend the tested deterministic pipeline to the two existing Pace-owned
recovery metrics before introducing any AI layer.

- [x] Add a 14-day data-quality gate for resting heart rate and a 7-day gate
  for sleep duration
- [x] Detect two adjacent resting-heart-rate days at least 5% above baseline
- [x] Detect one sleep duration at least 10% below baseline
- [x] Keep resting heart rate and sleep independent; do not create a combined
  readiness score or a context check-in for either signal
- [x] Show Garmin training readiness, Body Battery, stress, and recovery time
  with source date and freshness, without Pace-owned rules or baselines
- [x] Extend the deterministic `rules evaluate` and `explain` outputs

### Batch I — AI assistance

Use AI only for language, discussion, and bounded reasoning over compact
structured input. Never send credentials, tokens, raw Garmin payloads, database
dumps, or unrelated context history.

- [x] Add an explicit, read-only `pace ask "question"` command
- [x] Build and test a minimized AI context that excludes context-note text and
  all Garmin raw payloads, credentials, tokens, and database dumps
- [x] Use one stateless Responses API call with `store=False`, no tools, and no
  locally persisted AI chat history
- [x] Read only `OPENAI_API_KEY` from the existing owner-only local secrets file
  when it is not already supplied by the terminal environment
- [x] Use `gpt-5.6-terra` with low reasoning effort for bounded Swedish
  conversation over verified Pace facts
- [x] Validate structured AI answers in Python before displaying them
- [x] Allow an AI-produced context-event draft only as an explicit, unsaved
  proposal; Pace never writes an AI answer or draft automatically

### Batch J — Advanced coaching

Consider planning, workout generation, research retrieval, and adaptive
recommendations only after the earlier layers have stable contracts and
evidence-backed product decisions.

### Batch J1 — Race and planning readiness

- [x] Store explicit upcoming run and ride races with A/B/C priority, desired
  time as a goal only, and per-race taper override
- [x] Default taper policy: A full, B partial, C none; permit an explicit
  override or restoration of the priority default
- [x] Add `pace plan readiness` with a 28-day contiguous Garmin-sync coverage
  requirement and explicit coverage facts
- [x] Treat active `pain` or `illness` as a planning blocker
- [x] Use general-goal mode when no upcoming race exists; do not block on it
- [x] Keep J1 read-only with respect to training plans: no workouts, plan
  versions, AI plan calls, or automatic changes

### Batch J2 — Deterministic performance history

Build Pace-owned facts about durable volume, frequency, long sessions,
progression, and sufficient Garmin performance evidence before introducing
pace, power, or zone targets into a plan.

#### J2A — Capacity profile

- [x] Add `pace capacity show` over the newest contiguous J1 Garmin-history
  range
- [x] Report only observed run/ride volume, frequency, longest activity,
  duration-based sport balance, fixed-window continuity, and inactive streaks
- [x] Preserve missing distance as unknown and exclude `other` activities
- [x] Reuse recovery coverage and active planning blockers without exposing
  private note text
- [x] Explicitly defer performance evidence, pace, power, zones, progression
  limits, and plan generation to later J2/J3 slices

#### J2B — Detailed Garmin evidence

- [x] Add an independently audited `pace performance sync` with the same
  maximum seven-day calendar window as the main Garmin sync
- [x] Fetch details only for already imported normalized `run` and `ride`
  activities; never request or retain route or chart data
- [x] Persist only approved scalar fields and normalized numeric split summaries
- [x] Add `pace performance show` over the latest twelve weeks with explicit
  detail coverage, missing-detail facts, and no performance target
- [x] Let the athlete explicitly link a same-day, same-sport Garmin activity
  to a stored race; all result values remain Garmin-derived
- [x] Keep generic activity names, manually entered personal bests, and ordinary
  training sessions out of the performance-evidence contract
- [x] Defer exact Pace-defined benchmark protocols and all pace, power, zone,
  capacity, and planning policy to J2C/J3 owner decisions

#### J2C — Performance readiness gate

- [x] Define owner-approved benchmark protocols: 5 km and 10 km run time
  trials, plus a 20-minute cycling power test with a 19–21 minute powered split
- [x] Mark a benchmark only after Python validates its sport and observable
  Garmin evidence; ordinary activities never become evidence automatically
- [x] Add `pace performance readiness` with separate run/ride results
- [x] Require verified same-sport race or benchmark evidence within 12 weeks
  and at least two same-sport activities in the last 14 days before a future
  AI plan may propose an intensity target
- [x] Keep Python responsible for eligibility and limitations; defer all target
  proposals, workout generation, and plan writing to J3

### Batch J3 — Reviewable short-horizon plan drafts

Create a block view to an explicit A-race and a detailed one- or two-week
draft. Capture structured pass outcomes and optional, explicitly shared
feedback for a later revision draft; never overwrite an accepted plan.

- [x] Store a local planning preference with availability and sport role, not
  self-reported performance volume or PB; let the coach decide session mix
  from selected facts rather than a fixed Python ratio
- [x] Use a rolling four-week general-goal block when no A-race is selected
- [x] Generate an explicit, stateless AI plan draft with a block outline and
  seven or fourteen detailed days
- [x] Send only selected normalized Pace facts, context metadata, and optional
  explicitly shared feedback; never raw Garmin data or context-note text
- [x] Validate plan dates, required session fields, health/history gates, and
  sport-specific intensity eligibility in Python before writing a draft
- [x] Accept a plan explicitly; preserve every prior version and mark only an
  accepted parent plan superseded after accepting its revision
- [x] Store `completed`, `completed_limited`, or `skipped` session feedback
- [x] Generate only a short new revision draft from an accepted plan; never
  overwrite the block outline or an accepted plan automatically
- [x] Support cycling distance, duration, and athlete-confirmed Garmin zone
  1–5 targets after two recent rides; let the coach decide zone distribution,
  retain the power-test requirement for cycling power, and never generate
  cycling pace
- [x] Persist a separate coach assessment with observed facts, inferences,
  rationale, uncertainties, and non-citation coaching principles for every new
  plan draft
- [x] Harden the current plan contract: structured numeric targets and Garmin
  zones, fact-catalog-only assessment references, Python availability checks,
  full block-outline coverage, immutable bounded revisions, and no acceptance
  of legacy/incomplete drafts
- [x] Add integrity gates around planning: stale Garmin-history blocking,
  SQLite foreign-key enforcement and upgrade checks, and migration cleanup of
  the superseded fixed weekly-run preference

### Batch J3.3 — Local plan presentation

- [x] Add readable terminal views for a full plan review and today's/next
  planned session without changing planning or coaching logic
- [x] Generate a self-contained, owner-only local HTML plan report without a
  web server, AI call, raw Garmin payload, or private note text
- [x] Keep reports Git-ignored and make the report a read-only view over a
  persisted plan, leaving acceptance, feedback, and revisions explicit

### Batch J3.4 — Safe race lifecycle

- [x] Permit correction or permanent removal only for unused future races
- [x] Preserve cancelled races as local audit history and exclude them from
  future planning and Garmin evidence linking
- [x] Protect races referenced by plans or Garmin evidence from factual rewrites
  and deletion; protect accepted-plan targets from cancellation

### Batch K1 — Curated coaching knowledge

Build a local, source-attributed knowledge library before treating an AI
coaching rationale as evidence-grounded. Start with human-reviewed Markdown
briefs and deterministic topic selection; defer embeddings and vector search
until the library is large enough to need them.

- [x] Add a checked-in local source catalog and reviewed Markdown briefs for
  progression, intensity, taper, HRV context, and run/cycle combination
- [x] Select at most three topic-relevant briefs deterministically for each
  AI question or plan draft; do not fetch the web at runtime
- [x] Send only selected brief claims, limitations, applicability, and source
  IDs to the model, never raw papers or the full library
- [x] Validate any plan/answer knowledge references against the selected IDs,
  while allowing a general coach assessment without a local reference; expose
  each brief through `pace knowledge list/show`
- [x] Keep the library human-reviewed and versioned with the repository;
  defer automatic ingestion, embeddings, and vector search

### Batch K2 — Plan-aware coach dialogue

- [x] Add a quick plan-aware question and a short-lived terminal dialogue over
  one accepted, active plan
- [x] Rebuild selected current facts on every turn and retain at most four
  in-memory dialogue turns, with no persisted AI chat history
- [x] Permit only a structured same-day keep, skip, or replacement *draft*;
  validate its plan session, date, availability, sport, zone, and target gates
- [x] Never write, accept, or overwrite a plan from dialogue; keep persistent
  changes behind the existing separate revision-draft flow
- [x] Decide and build how athlete-selected coaching ambition
  (Försiktig/Balanserad/Offensiv) affects coaching judgment

### Batch K3 — Athlete-selected coaching ambition

- [x] Store `cautious`, `balanced`, or `ambitious` with default balanced for
  existing athletes and expose a one-command update
- [x] Send the ambition preference to plan drafting and coach dialogue
- [x] Keep it as model-owned coaching intent, never as a hard Python volume or
  intensity rule, and require the coach to explain its effect or limitation
- [x] Preserve every existing factual, availability, intensity-evidence, draft,
  and explicit-acceptance boundary

### Release Batch L0 — Private invited-friend alpha

- [x] Replace the developer-specific AI secret default with one Git-ignored,
  owner-only `.local/pace.env` per local clone
- [x] Add a safe key-file template and a simple from-zero README
- [x] Add the MIT license selected by the owner
- [x] Add GitHub Actions checks for a locked install, Ruff, and the synthetic
  test suite; never run live Garmin or OpenAI commands in CI

### Batch L1 — Explicit feedback trends

- [x] Add optional RPE 1–10 for completed/limited sessions and an optional
  structured reason for limited/skipped sessions; keep free-text local by
  default
- [x] Calculate deterministic, text-free two-window (28 day) trend facts from
  explicit feedback only; require six recent records and four prior records
  before comparisons
- [x] Expose `pace trends show` and send the bounded profile to plan drafts,
  revisions, and plan-aware coach dialogue without automatic plan changes
- [x] Make missing feedback an explicit limitation, never an inferred skipped
  session or causal claim

### Batch L2 — Dense local dashboard

- [x] Add `pace dashboard`, a current owner-only static HTML/SVG view over
  existing local facts, with no web server, AI call, or mutation
- [x] Show 28-day training, recovery, feedback, context, plan, and data-quality
  information without raw Garmin payloads or private note text

### Batch L3 — Bounded personalisation

- [x] Add a deterministic 56-day explicit-feedback evidence gate: 12 records
  overall and four records for same-sport observations
- [x] Let the athlete explicitly accept or archive a plan-derived coach
  principle; mark accepted principles for review after 84 days
- [x] Supply only current evidence and non-expired athlete-confirmed principles
  to plan drafting and plan-aware dialogue; never auto-change a plan

### Batch M1 — Explicit weekly coach review

- [x] Add one explicit stateless AI weekly review over selected local facts
- [x] Render an owner-only local HTML report without plan mutation, raw Garmin
  payloads, or private note text

### Batch M1.1 — General coach reasoning with factual boundaries

- [x] Treat supplied Pace data as the complete athlete-specific factual
  contract, while allowing the model to use general endurance-coaching knowledge
  for explicitly separate coach assessments and recommendations
- [x] Make curated local briefs optional support rather than a hard knowledge
  allowlist; retain only references to selected local briefs
- [x] Preserve deterministic facts, Python target/availability gates, medical
  boundaries, stateless calls, and explicit plan acceptance
- [x] Render weekly reviews with separate Pace-fact and coach-assessment
  sections so the user can see which kind of claim is being made

### Batch K1.1 — Broadened reviewed coaching library

- [x] Expand the checked-in, source-attributed local brief library from five to
  fifty reviewed briefs across
  workout structure, cycling periodisation, strength, HRV, sleep, recovery,
  pacing, taper, and run/cycle transfer
- [x] Expand deterministic topic selection to at most five relevant briefs;
  still no runtime web search, raw-paper storage, embeddings, or vector search
- [x] Keep source briefs as optional evidence support: athlete-specific facts
  remain the only factual contract crossing into an AI decision

### Batch J4.1 — Structured workout prescription

- [x] Store an ordered workout contract on every new planned session:
  warmup, steady work, intervals with explicit repetitions/recovery, and cooldown
- [x] Apply the existing target-evidence gates to every work and recovery block
  and bump the immutable plan contract to v3; older plans remain readable but
  must be regenerated before revision
- [x] Render the detailed workout structure in terminal and local HTML plan views

### Batch J4.2 — Explicit workout evaluation

- [x] Add a read-only comparison of a planned session, explicit athlete feedback,
  and same-day same-sport Garmin activity candidates
- [x] Never infer completion from Garmin or mutate a plan; pass evaluation and
  structured feedback only inform a separate explicit revision draft

### Batch J4.3 — Readable workout presentation and minimal block design

- [x] Render plan sessions as readable workout cards with separate work,
  recovery, target, and instruction fields instead of a single dense text cell
- [x] Make simple continuous sessions one steady block by default; warmup and
  cooldown are optional coaching tools, not required pass decoration

### Batch J5 — Rolling plan checkpoint

- [x] Add a read-only checkpoint over the active accepted plan, its detailed
  window, and races in the next 21 days
- [x] Recommend a new draft or bounded 14-day revision only when it can cover
  the approaching race or the current window is ending; never create, accept,
  or overwrite one automatically

### Batch J6 — Fact-led workout composition

- [x] Make the coach model choose continuous, progressive, hill, threshold, or
  interval structure from current facts and block purpose instead of rotating
  templates for artificial variety
- [x] Require an active race inside the detailed window to appear as a
  same-date, same-sport session while preserving its A/B/C priority
- [x] Keep every existing Python gate for availability, evidence, target type,
  cycling zones, and explicit plan acceptance

### Batch J7 — Split-aware workout comparison

- [x] Compare planned duration, distance, and interval repetitions with
  privacy-minimized same-day Garmin details and normalized splits
- [x] Keep the comparison read-only and explicitly limited: splits do not prove
  interval compliance and athlete feedback remains the authoritative outcome

### Batch L4 — Observed personalisation patterns

- [x] Derive non-causal completion, RPE, reason, and same-sport observations
  only after the existing 56-day feedback thresholds are met
- [x] Keep missing feedback unknown and prevent observed associations from
  becoming automatic plan changes or claims about causes

### Batch M2 — Pace Home and transparent analysis

- [x] Add `pace home`, one owner-only local entry page linking the current
  dashboard, active plan, weekly review, races, checkpoint, and personalisation
- [x] Add `pace analysis show` with inspectable 28-day duration, distance,
  frequency, explicit feedback/RPE, and recovery coverage
- [x] Do not invent a proprietary training-load score or convert missing
  distance into zero

### Batch N1 — Synthetic coach evaluation

- [x] Add six reviewed synthetic coaching scenarios with no real athlete data,
  Garmin access, credentials, or required network call
- [x] Run the deterministic fake-coach contract in the normal test suite
- [x] Keep real model evaluation explicit behind `pace eval coach --live`; it
  performs six synthetic OpenAI calls and never runs in CI

## Explicitly deferred

- Multi-user accounts
- Cloud deployment
- Web or mobile UI
- Background sync scheduling
- Automatic unbounded Garmin backfill
- Automatic Garmin deletion reconciliation
- Append-only raw ingestion history
- Application-level SQLite encryption
- Embeddings and vector search
- Garmin workout export
- Medical or clinical interpretation
