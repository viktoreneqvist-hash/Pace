# Architecture Decisions

This file records important technical and product decisions.

A decision should be changed only intentionally.

When changing a decision:
- explain the previous problem
- explain alternatives
- document why the new choice is better
- describe consequences

---

# Decision #1

## Problem

Python dependency and project management.

## Options

- pip + venv
- uv

## Chosen

uv

## Reason

uv provides a modern Python workflow with:

- fast dependency resolution
- reproducible environments
- integrated project management
- simpler developer experience

## Consequences

The project needs to understand:

- pyproject.toml
- uv.lock
- virtual environments
- dependency management

---

# Decision #2

## Problem

Primary data source.

## Options

- Strava
- Garmin Connect
- Both

## Chosen

Garmin Connect only for v1.

## Reason

The goal is a personal endurance coach, not an activity sharing application.

Garmin provides more coaching-relevant information:

- activities
- heart rate
- HRV
- resting heart rate
- sleep
- stress
- Body Battery
- training readiness
- recovery metrics
- device-specific metrics

Strava mainly provides activity and social data.

For understanding athlete condition, Garmin is the stronger foundation.

## Consequences

The system will:

- remove Strava integration
- focus the data model around Garmin
- avoid maintaining multiple providers
- simplify synchronization

A future multi-provider architecture is possible, but not needed for a private v1 system.

---

# Decision #3

## Problem

Database selection.

## Options

- SQLite
- PostgreSQL
- MongoDB

## Chosen

SQLite for v1.

## Reason

The project is:

- single-user
- local-first
- private
- low concurrency

SQLite provides:

- minimal setup
- easy backups
- simple inspection
- excellent support for local applications

The previous PostgreSQL decision was made to learn production-style backend infrastructure. That was valuable, but the product direction has changed.

The current goal is proving the coaching system, not building multi-user infrastructure.

## Consequences

Benefits:

- faster development
- easier debugging
- simpler deployment

Trade-offs:

- less production-like experience
- migration would be needed if moving to a multi-user cloud system

---

# Decision #4

## Problem

When should AI be introduced?

## Options

- Use AI from the beginning
- Build deterministic systems first

## Chosen

Deterministic calculations before AI.

## Reason

Training metrics must be:

- reproducible
- testable
- explainable
- inexpensive

Examples:

Python calculates:

- distance
- volume
- trends
- HRV baseline
- deviations
- training load

AI explains and discusses results later.

## Consequences

The system must function without an LLM first.

AI becomes a reasoning layer, not a calculation engine.

---

# Decision #5

## Problem

How should athlete context be stored?

## Options

- Only use chat history
- Store notes as unstructured text
- Create structured context memory

## Chosen

Structured context events.

## Reason

Athlete life affects interpretation of physiological data.

Examples:

HRV decrease could be:

- training fatigue
- illness
- alcohol
- poor sleep
- stress
- travel

The system needs queryable historical context.

## Consequences

Create a dedicated context event model containing:

- event type
- dates
- description
- severity
- affected metrics
- confidence

---

# Decision #6

## Problem

Initial user interface.

## Options

- Web application
- Mobile application
- CLI

## Chosen

CLI first.

## Reason

The first goal is understanding and building the system.

CLI provides:

- fast iteration
- easier debugging
- fewer infrastructure concerns

The underlying services can later support another interface.

## Consequences

No frontend development in v1.

---

# Decision #7

## Problem

How should coaching intelligence be structured?

## Options

- Direct LLM analysis of raw data
- Rule-based interpretation first
- LLM-first agent

## Chosen

Metrics → Context → State → Rules → AI.

## Reason

A coach needs a reliable understanding of the athlete before generating recommendations.

Architecture:


## Consequences

The LLM receives structured information rather than raw history.

This improves:

- reliability
- cost
- explainability
- testing

---

# Decision #8

## Problem

What is the product?

## Options

- Training report generator
- AI chatbot
- Persistent coaching system

## Chosen

Persistent coaching system.

## Reason

Reports become outdated immediately.

A coach needs memory:

- previous injuries
- previous races
- training history
- athlete preferences
- corrected interpretations

## Consequences

Memory is a core feature, not an optional addition.

---

# Decision #9

## Problem

How should raw external data be handled?

## Options

- Only store processed values
- Store raw payloads

## Chosen

Store raw Garmin payloads.

## Reason

External APIs change.

Raw data allows:

- debugging
- reprocessing
- improved normalization later
- auditing

## Consequences

Storage requirements increase slightly.

---

# Decision #10

## Problem

The existing codebase was named `running_agent`, used PostgreSQL, and contained a
Strava integration. This conflicted with the Garmin-only, local-first Pace v1 direction.

## Options

- Continue extending the existing Strava-oriented structure
- Maintain both Strava and Garmin providers
- Preserve the historical version and reset the active codebase around Pace

## Chosen

Create an archived Git branch and annotated tag for the final Strava version, then rename
the active package to `pace`, remove Strava code, and use SQLite as the local default.

## Reason

Pace v1 needs recovery data and deterministic coaching foundations, not multiple provider
maintenance. Keeping the archive reference preserves the earlier learning work and makes
the migration reversible without retaining unused runtime code.

## Consequences

- `archive/strava-v0.1.0` and `strava-final-v0.1.0` preserve the pre-migration state.
- Garmin becomes the only external-provider boundary in the active codebase.
- Future Garmin authentication and synchronization build on `pace.integrations.garmin`.
- The packaged command is `pace`; the former standalone `main.py` entry point is removed.

---

# Decision #11

## Problem

Pace needs a safe way to evolve its local SQLite schema as activities, recovery
metrics, context events, and synchronization history are introduced over time.

## Options

- Create tables directly from SQLAlchemy models on every application start
- Maintain SQL files manually
- Use versioned Alembic migrations generated from SQLAlchemy metadata and reviewed in Git

## Chosen

Use Alembic migrations for the Pace SQLite schema.

## Reason

Migration files make schema changes explicit, repeatable, and reviewable. They
allow a local Pace database to move safely from one version to the next without
requiring the user to delete existing training data.

## Consequences

- Each schema change requires a reviewed migration file.
- Tests apply the real migrations to an isolated SQLite database.
- The application must not use `Base.metadata.create_all()` as its normal setup path.
- The initial migration creates `activities`, `daily_metrics`, `context_events`, and `sync_runs`.

---

# Decision #12

## Problem

Pace needs a Garmin client that can authenticate interactively once, persist a
local session safely, and make a small first synchronization without coupling
the rest of the application to Garmin-specific APIs.

## Options

- Use the legacy `garth` package directly
- Copy the older client from the reference project
- Use the maintained `garminconnect` client behind a small Pace wrapper

## Chosen

Use `garminconnect` 0.3.6 behind `pace.integrations.garmin.client`.

## Reason

The current library owns Garmin's authentication flow, MFA prompt, token
refresh, retry limits, and token-file permissions. Pace retains a small
provider boundary, so authentication errors and raw provider details do not
spread into the CLI, database, or future coaching logic.

## Consequences

- `pace garmin login` asks for the password only in the terminal and never
  saves it to Pace's database or repository.
- Reusable tokens are stored in `.local/garmin_tokens/`, which is Git-ignored;
  Pace enforces owner-only directory and token-file permissions.
- `pace sync --days 7` imports activities and available daily recovery data
  and records the result in `sync_runs`.
- Pace translates provider authentication, connection, and rate-limit failures
  at the integration boundary before they reach the CLI.

---

# Decision #13

## Problem

Daily recovery data comes from several independent Garmin endpoints. Devices
and subscriptions do not always expose every signal, and a failed recovery
endpoint must not discard a successful activity synchronization.

## Options

- Fail the entire sync when any recovery endpoint is unavailable
- Store each endpoint in a separate table and sync run
- Store one normalized daily record and mark the provider sync as partial

## Chosen

Use one `daily_metrics` record per date and one `sync_runs` record per Pace
sync. Import resting heart rate, stress, and Body Battery from Garmin's daily
summary; import sleep, HRV, and training readiness from their specific
endpoints. Mark the sync `partial` when recovery data is incomplete.

## Reason

The daily summary avoids extra requests for signals it already contains.
Separating endpoint failures preserves useful facts while keeping the audit
trail honest. The stored training-readiness score uses Garmin's wake-up
snapshot when present, because it is the day's pre-training baseline; the
latest snapshot is only a fallback.

## Consequences

- `pace sync --days 7` now imports available daily recovery signals alongside
  activities.
- The first recovery import may require several read-only Garmin requests per
  day, so rate limiting stops further recovery calls and yields a partial run.
- Missing device features produce nullable metric fields, not invented values.
- Raw successful provider payloads are retained in the daily metric for
  debugging and future re-normalization. A failed endpoint cannot erase its
  previous successful normalized values or raw snapshot.

---

# Decision #14

## Problem

Pace needs factual, reproducible training and recovery summaries before it can
interpret fatigue or recommend training. The system must not hide arbitrary
coaching thresholds inside its first calculations.

## Options

- Calculate only total activity volume
- Introduce training-load and readiness rules immediately
- Build explicit rolling summaries first, then add interpretation later

## Chosen

Build deterministic summaries with two seven-day training windows and a
28-day recovery baseline. The recovery baseline is the arithmetic mean of all
available daily values in the trailing 28 calendar days. HRV, resting heart
rate, and sleep duration expose their data-point counts alongside the values.

## Reason

Two adjacent seven-day windows make volume changes transparent without calling
them good or bad. A 28-day window is stable enough to become a personal
reference as history accumulates, while explicit data counts prevent a short
history from masquerading as a complete baseline.

## Consequences

- `pace metrics summary` reports running distance, cycling duration, total
  duration, activity and active-day counts, longest run/ride, and change from
  the preceding seven-day window.
- The same command reports 28-day baseline, seven-day average, latest value,
  and percentage deviation for HRV, resting heart rate, and sleep duration.
- A zero previous training volume yields no percentage change rather than an
  invented infinite increase.
- Activity instants remain stored in UTC, but calendar windows use the fixed
  athlete timezone `Europe/Stockholm`.
- No thresholds, risk labels, or coaching recommendations are created in this
  batch; those belong to the later athlete-state and rule-engine phases.

---

# Decision #15

## Problem

UTC activity timestamps do not by themselves define the athlete's intended
calendar day around midnight.

## Options

- Use UTC dates everywhere
- Store a local date on every activity
- Store UTC instants and derive dates in one configured athlete timezone

## Chosen

Store UTC instants and derive query and analysis dates in
`Europe/Stockholm`. V1 does not change activity timezone during travel; travel
can remain an ordinary context event.

## Reason

The athlete trains in one timezone. Deriving the date at the boundary fixes the
real midnight error without duplicating date fields or building a travel model.

## Consequences

- Repository date ranges convert Stockholm day boundaries to UTC.
- Deterministic training windows classify each activity by Stockholm date.
- Changing the timezone is a configuration decision; historical rows do not
  require migration.

---

# Decision #16

## Problem

Garmin exposes many activity profiles, while Pace v1 is only intended to
calculate running and cycling facts.

## Options

- Count every Garmin activity in total training
- Maintain many internal sport families
- Recognize running and cycling explicitly and exclude everything else

## Chosen

Normalize known running profiles to `run`, known cycling profiles to `ride`,
and every other or unknown profile to `other`. Only `run` and `ride` count in
training totals, activity counts, active days, longest sessions, or
comparisons.

## Reason

Strict inclusion prevents an unfamiliar Garmin profile from silently changing
Pace's facts. It implements the product scope with one small internal contract.

## Consequences

- Unrelated activities remain locally stored for traceability but are
  analytically irrelevant.
- A new Garmin running or cycling profile must be deliberately added to the
  normalizer and covered by a synthetic test before it counts.
- No goal priority or running/cycling allocation is inferred.

---

# Decision #17

## Problem

Large historical syncs multiply daily Garmin requests and make rate limits,
partial progress, and troubleshooting harder.

## Options

- Allow arbitrary date ranges
- Add persistent cursors, background jobs, and automatic retries
- Use small explicit, idempotent history batches

## Chosen

Limit one CLI sync to at most seven inclusive days. Use `--end-date` to select
older seven-day batches and safely repeat a batch when needed.

## Reason

Bounded manual batches are enough for one local user. Idempotent upserts and
`sync_runs` provide safe recovery without a scheduler or checkpoint subsystem.

## Consequences

- Rate limiting stops the remaining recovery range and returns a retryable exit
  code without aggressive automatic retries.
- Already fetched values for the current day are saved before a stop.
- Importing long history requires several explicit commands.

---

# Decision #18

## Problem

A partial recovery resync can receive fresh data from some Garmin endpoints
while another endpoint fails. Replacing the whole daily row would erase the
last known good values from the failed endpoint.

## Options

- Replace the entire daily row on every sync
- Add append-only provider-ingestion tables and versioned snapshots
- Update normalized fields and raw payload independently by successful endpoint

## Chosen

Keep one daily row and the latest successful raw snapshot per endpoint. Update
only fields owned by endpoints that completed. Preserve previous values and raw
data for endpoints that failed; a successful empty response explicitly clears
that endpoint's old values.

## Reason

Endpoint-scoped merging prevents data loss and retains useful debugging
provenance without introducing a second ingestion schema.

## Consequences

- `partial` means available facts were committed and failed endpoint facts were
  not overwritten.
- Re-running the same payload reports zero updated rows.
- Full historical raw versions are not retained; add append-only ingestion only
  if a concrete audit or reprocessing need appears.

---

# Decision #19

## Problem

The local database and Garmin session are sensitive, but Pace runs for one user
on a computer without untrusted local accounts.

## Options

- Rely only on default filesystem modes
- Enforce owner-only files and rely on operating-system disk protection
- Add SQLCipher and application-managed encryption keys

## Chosen

Use mode `0700` for Pace-owned private directories and `0600` for the SQLite
database and Garmin token file. Rely on the operating system's disk protection;
do not add application-level encryption or key management in v1.

## Reason

Owner-only permissions close accidental local exposure and Git ignores prevent
commits. SQLCipher would add key lifecycle, migration, backup, and support
complexity without addressing a stated threat.

## Consequences

- `data/`, `.local/`, database sidecars, and tokens remain outside version
  control.
- Password and MFA input use hidden terminal prompts.
- Raw Garmin payloads remain local and must never be copied into future AI
  context.

---

# Decision #20

## Problem

An activity can disappear from a later Garmin response because it was deleted,
because the requested range behaved differently, or because the provider
response was incomplete. Pace must decide whether absence is a delete signal.

## Options

- Treat Pace as an append/update local archive
- Hard-delete any local activity absent from a successful batch response
- Add tombstones and a separate reconciliation workflow

## Chosen

Treat v1 as an append/update local archive. Upsert returned activities, but
never infer deletion from provider absence.

## Reason

Automatic deletion is the only destructive option and requires stronger proof,
audit counts, and date-range guarantees than the current Garmin boundary
provides. A tombstone workflow would add schema and product complexity for an
unobserved v1 use case.

## Consequences

- Garmin edits to an existing activity update its local row.
- A Garmin-deleted activity remains local and can continue to affect facts.
- If deletion becomes a real need, add an explicit local exclude/delete command
  or an auditable reconciliation design rather than silently hard-deleting.

---

# Decision #21

## Problem

Pace needs athlete-provided facts that Garmin cannot observe, but an open-ended
note by default would incorrectly make a one-night event or one drink appear
relevant forever.

## Options

- Store free-form notes without types or dates
- Make every context event open-ended until manually closed
- Use a small typed contract with finite notes by default and explicit ongoing
  events

## Chosen

The first context-memory slice supports `illness`, `pain`, `travel`,
`alcohol`, `poor_sleep`, `work_stress`, and `schedule_constraint`.

Every note requires a type, start date, and private description. A note without
an end date closes on the start date. `--ongoing` explicitly creates an active
event with no end date; a finite range uses `--end-date`.

## Reason

This captures the most useful non-Garmin context while keeping terminology
small and avoiding diagnostic injury semantics. Explicit lifecycle behavior
prevents accidental long-lived context from influencing later state or rules.

## Consequences

- `pace note add` stores a validated event without interpreting its effect on
  training or recovery.
- `pace note list --from ... --to ...` returns only events overlapping the
  requested date range.
- `severity`, `confidence`, and `affected_metrics` stay available in the data
  model but are not required from the athlete in this first CLI slice.
- Context notes remain local and are not automatically sent to a future AI
  model.

---

# Decision #22

## Problem

Rules and future AI assistance need one compact, auditable representation of
Pace's current facts. Reconstructing training facts, recovery coverage, sync
status, and relevant context separately in each consumer would duplicate data
selection logic and make omissions difficult to notice.

## Options

- Let every future rule or interface query the database independently
- Persist mutable athlete-state rows in a new database table
- Build a dynamic, read-only structured snapshot from the stable v1 layers

## Chosen

`pace state show` builds an `AthleteState` dynamically in Python. It contains
the existing deterministic metric summary, context events overlapping the
current seven-day training window, and data-quality facts: the latest completed
sync record plus observed recovery coverage counts.

Context events are included only when they overlap the current window. An
explicitly ongoing event overlaps that window until it is closed. State exposes
facts such as a partial sync or incomplete baseline; it does not assign a
readiness score, infer physiology, or make coaching recommendations.

## Reason

The existing source tables already contain the canonical facts, and state is a
small derived view. Dynamic construction avoids cache invalidation and a new
migration while keeping the exact selection contract visible and testable.

## Consequences

- No athlete-state table or migration is added in Batch F.
- Rules and later bounded AI input receive one compact contract rather than raw
  database rows or Garmin payloads.
- `--end-date` makes historical snapshots reproducible without Garmin calls.
- Goal priority, sport allocation, pain limits, intensity distribution, and
  training progression remain explicit future owner decisions.

---

# Decision #23

## Problem

Pace needs its first transparent interpretation rule without treating a short
HRV history, a single below-baseline value, or an unrelated life event as a
coaching or medical conclusion.

## Options

- Add several readiness and training rules immediately
- Interpret any single HRV value below its baseline
- Add a small data-quality gate and one explicit HRV-plus-context rule

## Chosen

Batch G evaluates two read-only Python rules through `pace rules evaluate`.
`hrv_baseline_data_quality` requires at least 14 observed HRV days in the
existing 28-day baseline window. `hrv_context_present` requires two consecutive
calendar days with HRV strictly below that same current baseline.

When that signal exists, the rule checks the signal date and two preceding
calendar days for only `poor_sleep`, `alcohol`, `travel`, `work_stress`, and
`illness`. `pain` and `schedule_constraint` are intentionally excluded from
this HRV rule. Rule JSON contains identifiers, normalized factual values,
selected context types, and explicit limitation codes; it contains neither
context-note text nor coaching prose or advice.

## Reason

The 14-day gate stops a short history from looking more certain than it is.
Requiring two calendar-adjacent observations reduces reactions to a single
value, while the small context set records plausible competing context without
claiming causality. Keeping the result structural makes every condition and
limitation inspectable before an explanation layer is added.

## Consequences

- A current 7-day HRV history yields `insufficient_data`, not a readiness
  label.
- A negative HRV pattern without selected context yields `not_triggered`, not
  a conclusion that training caused it.
- The current 28-day baseline remains the comparison value; this batch does
  not introduce a second or clinical baseline calculation.
- Athlete state carries only the current seven-day window's normalized HRV
  observations, allowing the rule layer to verify calendar adjacency without
  querying raw Garmin payloads or reconstructing state independently.
- Future rules for pain, schedule constraints, training load, goals, and
  planning require separate owner decisions.

---

# Decision #24

## Problem

Raw rule JSON is auditable but difficult to use as a daily coaching interface.
Pace also needs a way to ask for missing athlete context without assuming a
cause, repeatedly interrogating the athlete, or silently saving sensitive
information.

## Options

- Send rule JSON directly to an LLM for every explanation
- Let an LLM choose when to ask follow-up questions
- Add deterministic templates and a narrowly gated, optional check-in

## Chosen

`pace explain` renders local Swedish templates from the existing rule results.
It does not calculate new metrics, change rule outcomes, call Garmin, or call
an LLM.

When `hrv_context_present` has the approved two-day HRV signal but no selected
context, Pace presents one neutral check-in about `poor_sleep`, `alcohol`,
`travel`, `work_stress`, or `illness`. It does not claim that any factor caused
the HRV pattern. It neither prompts interactively nor saves a response; the
athlete explicitly uses `pace note add` to store context.

## Reason

Deterministic templates make the existing rule evidence readable while keeping
the wording bounded and inspectable. The narrow gate avoids asking about every
ordinary HRV change. Explicit note creation keeps the athlete in control of
sensitive information and provides a safe foundation for a future conversational
interface.

## Consequences

- `pace rules evaluate` remains the source for structured audit output.
- `pace explain` is an optional local presentation layer, not a coach that
  gives training advice.
- A future LLM may improve wording and understand free text, but Python retains
  control over when a check-in is eligible and the athlete must confirm any
  structured context event before storage.

---

# Decision #25

## Problem

Pace already calculates baselines for resting heart rate and sleep duration,
and stores several Garmin-owned status values. Before an AI layer is added, the
system needs to extend its own deterministic coverage without turning multiple
signals into an opaque readiness score or double-counting Garmin's proprietary
interpretations.

## Options

- Build an AI layer before expanding deterministic recovery coverage
- Combine HRV, resting heart rate, sleep, and Garmin scores into one readiness
  value
- Add separate, explicit resting-heart-rate and sleep rules while displaying
  Garmin-owned values as dated facts only

## Chosen

Resting heart rate requires 14 observed baseline days. Sleep duration requires
7 observed baseline days because one night's duration is a more immediate,
discrete signal. The resting-heart-rate rule requires two adjacent calendar
days at least 5% above its own current baseline. The sleep rule requires one
latest sleep duration at least 10% below its own current baseline. Both
outcomes are observations only; they produce neither a context check-in nor a
training recommendation.

Training readiness, Body Battery, average stress, and recovery time remain
Garmin-owned values. Pace shows their latest local value, source date, and
whether it belongs to the requested state date. It does not create baselines,
rules, or a combined score from them.

## Reason

Resting heart rate and sleep already have Pace-owned, reproducible metrics, so
they are the smallest reliable expansion of the verified pipeline. A 5% two-day
resting-heart-rate threshold filters small day-to-day variation. A single sleep
duration can be a meaningful discrete night, so its observation gate can start
after seven days; the 10% threshold still avoids treating a few minutes of
variation as a signal. Garmin's composite values may already incorporate
overlapping data, so using them as separate Pace rule input would obscure
provenance and risk double-counting.

## Consequences

- `pace rules evaluate` reports separate evidence for HRV, resting heart rate,
  and sleep duration; no result is a recovery or readiness score.
- `pace explain` presents the three Pace-owned signal chains independently.
- Garmin status is visible but never changes a Pace rule result.
- Active exercise heart rate, pulse zones, intensity, training load, pain, and
  goal-aware recommendations remain later explicit product decisions.

---

# Decision #26

## Problem

Pace needs a first conversational AI interface without giving an external model
raw Garmin data, private context-note text, authority to alter local state, or
responsibility for deterministic coaching facts.

## Options

- Send the full `pace state show` output and let an LLM answer freely
- Add an autonomous AI agent with database and note-writing tools
- Add one explicit, stateless, read-only question command over selected Pace facts

## Chosen

Add `pace ask "question"` as the first AI slice. It builds a compact
`AIContext` in Python from deterministic metrics, selected context event
metadata, data quality, Garmin-owned dated facts, rule evaluations, and
deterministic explanations. Context-note text, raw Garmin payloads,
credentials, tokens, database dumps, and prior conversations are excluded.

The command uses `gpt-5.6-terra` with low reasoning effort through the
Responses API. Each request is independent and sets `store=False`; Pace stores
no AI chat history. The model has no tools and cannot write to SQLite. Its
structured answer is validated in Python before display. It may return a typed
context-event draft only when the athlete explicitly supplies new context; the
draft is never stored automatically.

## Reason

The stable metrics, state, rules, and deterministic explanations already form a
small auditable fact boundary. A read-only conversational layer can improve
language and discussion without changing Pace's canonical evidence or privacy
model. Stateless calls and minimal selected context limit retention, cost, and
the chance of unrelated history influencing an answer.

## Consequences

- AI assistance reads `OPENAI_API_KEY` from the terminal when supplied there;
  otherwise it reads only that key from the owner-only local default file
  `../secrets/running-agent.env`. `PACE_OPENAI_SECRETS_FILE` can select another
  owner-only file. The key remains ignored by Git and is never printed.
- An AI call happens only when the athlete explicitly runs `pace ask`; syncs
  and deterministic commands never trigger it.
- Python still owns calculations, data quality, and all rule outcomes.
- AI answers are not medical diagnoses or training recommendations in this
  slice.
- A context draft must be reviewed and saved separately with `pace note add`.
- Weekly AI reviews, planning, tools, chat memory, retrieval, and HTML reports
  remain future decisions.

---

# Decision #27

## Problem

Pace needs to prepare for future plan generation without trusting
self-reported training volume or personal bests as evidence, quietly choosing
race priorities, or generating a plan while an active pain or illness event is
known.

## Options

- Ask the athlete for a static volume, personal-best, and availability profile
- Let an LLM infer races, capacity, and taper policy from conversation alone
- Store explicit upcoming races, measure imported Garmin coverage in Python,
  and expose a read-only readiness gate before any plan generation

## Chosen

Batch J1 adds local `races` and `pace plan readiness`.

An upcoming race has sport, date, distance, A/B/C priority, an optional desired
time, and an optional taper override. Priority defaults are full taper for A,
partial taper for B, and no taper for C. An athlete can explicitly override a
single race or restore the priority default. Desired time is an athlete goal,
not evidence of current capacity.

`pace plan readiness` requires 28 contiguous locally recorded Garmin-sync
calendar days. It treats completed `success` and `partial` sync windows as
coverage, reports their exact date range, and blocks planning for active
`pain` or `illness` events. No upcoming race is a general-goal mode, not a
blocker. J1 creates no workouts or plan versions.

## Reason

Future Pace planning must be constrained by actual recent history. A visible
readiness gate prevents a short or unknown import window from looking like a
complete baseline, and it makes known health context an explicit stop condition
instead of a hidden prompt instruction. Race intent remains athlete-owned while
capacity remains a later deterministic analysis problem.

## Consequences

- Pace does not ask the athlete to manually declare previous volume or PB as a
  planning fact.
- Multiple A/B/C races can be stored; selecting a block-defining A race belongs
  to the later plan-draft decision.
- A one-day stale analysis date can still use the newest completed sync end
  date; readiness reports that end date instead of pretending today's data was
  imported.
- J2 must add deterministic performance-history facts before Pace can issue
  pace, power, or zone targets.
- J3 may create only reviewable short-horizon plan revisions; it must never
  overwrite an accepted plan automatically.

---

# Decision #28

## Problem

Future Pace plans need a truthful representation of what the athlete has
actually completed. A generic fitness score, a self-reported volume, or an LLM
estimate would hide the source facts that must constrain future planning.

## Options

- Let the future plan model infer capacity directly from raw activity history
- Store a single opaque readiness or fitness score
- Build a deterministic, inspectable capacity profile over the J1 imported
  history before any performance targets or plans exist

## Chosen

Batch J2A adds `pace capacity show`. It reports only normalized `run` and
`ride` facts over the newest contiguous imported Garmin range selected by J1:
per-sport activity count, active days, duration, complete-or-unknown distance,
longest activity, duration-based run/ride split, fixed seven-day continuity,
and longest inactive calendar streak.

It reuses existing recovery coverage facts and J1 race/blocker facts. It does
not calculate a combined score, pace target, zone target, training load, or
future volume. It explicitly reports `performance_targets_pending_j2c` because
J2A itself does not set pace, power, zone, capacity, or plan targets.

## Reason

The profile gives a future bounded planner a compact factual contract while
keeping every underlying observation visible. Duration is the only shared unit
for run/ride balance; distances are retained per sport and remain unknown when
any source distance is missing. This avoids a false comparison between running
distance and cycling distance.

## Consequences

- A zero-activity week and a long inactive streak remain visible evidence, not
  missing data to be filled by an LLM.
- Active pain or illness does not hide capacity history, but marks the profile
  as blocked for future plan generation.
- J2B must fetch and normalize approved detailed run/ride evidence before Pace
  can validate race or later benchmark claims; J2C remains responsible for the
  jointly decided target policy.
- J3 may use the profile as a boundary, but the exact progression envelope is
  a separate explicit coaching-policy decision.

---

# Decision #29

## Problem

Pace needs detailed Garmin performance evidence for future targets and plans,
but full activity-detail payloads can contain route coordinates and dense chart
streams. Ordinary training activities and self-reported personal bests are not
reliable proof of performance capacity.

## Options

- Retain every detailed Garmin payload and infer performance from any activity
- Ask for manual personal bests and let an LLM estimate capacity
- Import a bounded, privacy-minimized detail contract and accept only explicit
  race links plus later owner-defined benchmark protocols as evidence

## Chosen

Batch J2B adds a separate, independently audited `pace performance sync`.
It uses the established maximum seven-day window and considers only already
imported normalized `run` and `ride` activities. The Garmin detail request
explicitly disables route and chart retrieval; Pace persists only selected
scalar fields and normalized numeric split summaries. No raw detail payload,
GPS coordinate, polyline, or second-by-second stream is retained.

`pace performance show` reports the last twelve weeks of eligible activity
detail coverage, missing detail facts, and explicit race evidence. A race
result exists only after the athlete links a detailed Garmin activity to a
stored race with matching Stockholm-local date and sport. Garmin remains the
source for observed result values; the athlete provides only the link.

The schema reserves a benchmark evidence type, but no benchmark can yet be
created. Exact Pace-defined benchmark protocols are a coaching-policy decision
and must be selected with the owner before J2C uses them for targets.

## Reason

This preserves the product's core promise: Pace should constrain future
planning with observed history rather than optimistic self-report or opaque
model guesses. A separate detail path limits both Garmin rate-limit exposure
and the sensitive data retained locally while keeping retries idempotent and
auditable.

## Consequences

- `pace sync` remains the normal activity and recovery import; it never starts
  a detailed backfill automatically.
- Re-running a performance-detail batch changes zero records when Garmin's
  selected facts are identical.
- A failed detail or split request preserves any previous valid detail for that
  activity. Rate limits and expired sessions stop the remaining batch after
  earlier successes are stored.
- Pace still produces no pace, power, zone, fitness, or training-plan target.
- J2C must jointly define benchmark protocols and evidence sufficiency before
  any performance target can be produced.

---

# Decision #30

## Problem

J3 needs to use actual performance evidence without converting an old race,
an arbitrary hard activity, or an LLM guess into a current intensity target.
Pace must distinguish evidence that is useful for general planning from
evidence that is current enough to justify a future pace, power, or zone
proposal.

## Options

- Let the planner infer performance from any Garmin activity or self-reported PB
- Use a single opaque fitness score to choose intensity targets
- Define explicit benchmark protocols and a sport-specific Python eligibility
  gate before an AI may propose intensity

## Chosen

J2C adds three Pace-defined benchmark protocols:

- `run_5k_time_trial`: an explicitly marked run between 4.75 and 5.25 km
- `run_10k_time_trial`: an explicitly marked run between 9.5 and 10.5 km
- `ride_20min_power_test`: an explicitly marked ride with a 19–21 minute
  Garmin split containing average power

The athlete still explicitly marks a completed protocol. Pace never infers a
benchmark from a name or ordinary activity. A valid race link remains separate
verified evidence.

`pace performance readiness` evaluates running and cycling independently. A
future AI plan may propose running pace or cycling power only when it has at
least one verified race or benchmark in the preceding 12 weeks and at least
two activities in that same sport during the preceding 14 calendar days.
Decision #32 adds the cycling heart-rate-zone exception. Python
reports eligibility, evidence date/count, current activity count, configured
zone facts, and limitations. It calculates no pace, power, fitness score,
workout, or plan.

## Reason

The old race can remain meaningful evidence, but it must not overrule an
extended break from the same sport. The two independent gates make this
visible: current sport continuity protects against overreaching, while the
explicit evidence requirement prevents a language model from inventing
capacity. The run and ride gates remain separate because their performance
signals are not interchangeable.

## Consequences

- A sport can be eligible for a conservative general plan while not eligible
  for an intensity target.
- An athlete can use a standard test to regain evidence after a break, but a
  manually named or self-reported result is never sufficient.
- J3 receives compact Python facts and may propose a conservative target only
  within the eligibility boundary; the athlete must still review any plan.
- The benchmark distance and time windows are validation tolerances, not
  performance targets or coaching prescriptions.

---

# Decision #31

## Problem

Pace needs to turn verified history, evidence, recovery gates, race intent, and
real availability into useful plans without treating self-reported performance
as fact, silently changing an accepted plan, or allowing an AI model to bypass
the safety boundaries established in J1–J2C.

## Options

- Generate a long autonomous plan from a chat prompt and overwrite it after
  every outcome
- Block planning until every sport has an intensity target
- Create a reviewable block and short-horizon AI draft within Python-owned
  gates, then store plan versions and feedback explicitly

## Chosen

J3 stores one local planning preference with available weekday/time slots and a
desired sport role: `run_primary`, `ride_primary`, or `balanced`. It does not
collect manual volume or PB claims. The LLM receives this feasibility input
together with compact selected Pace facts and proposes the actual allocation
from observed history.

`pace plan draft` is an explicit, stateless AI call. It creates a persisted
`draft` only after Python confirms J1 readiness, no active health blocker, a
saved planning preference, valid dates, and Python-owned intensity eligibility.
Decision #32 is the narrow cycling-zone exception. An
explicit A-race defines the block when selected; no race uses a rolling
four-week general-goal block. Only the first seven or fourteen days are
detailed. The LLM output is strict JSON and Python rejects a pace, power, or
heart-rate-zone target for a sport that Python has not approved. Such a sport may still receive a
conservative general session using RPE or no intensity target.

The athlete accepts a draft explicitly. Sessions then accept one outcome:
`completed`, `completed_limited`, or `skipped`. Optional feedback text stays
local by default. A revision request sends a note only when that individual
feedback record was explicitly marked shareable, creates a new short draft, and
retains the original block outline. Accepting a revision marks its accepted
parent `superseded`; no plan version is deleted or changed in place.

## Reason

This lets Pace offer the useful part of coaching — a concrete, adaptive next
one or two weeks — without pretending that a language model owns physiology,
planning facts, or user intent. The durable block gives the athlete context,
while the detailed horizon remains responsive to real completion and recovery.

## Consequences

- J3 plan generation needs the existing local OpenAI API-key configuration but
  never runs during sync, metrics, or deterministic commands.
- `gpt-5.6-terra` uses medium reasoning effort only for an explicit plan or
  revision draft, with `store=False`, no tools, and no chat history.
- The first J3 interface remains CLI/JSON; HTML and web/mobile presentation are
  separate UX work, not a prerequisite for safe planning.
- Pace has no fixed numerical progression cap yet. J2A/J2C facts and explicit
  gates constrain the model now; any universal volume/progression policy must
  be a future shared coaching decision.

---

# Decision #32

**Status: superseded in part by Decision #34.** The verified Garmin-zone
contract and no-cycling-pace boundary remain; the fixed zone distribution does
not.

## Problem

The athlete uses cycling as primary endurance training but has no cycling race
evidence and does not plan to race cycling. Pace still needs a useful, safe
cycling target that does not invent a speed or power capacity.

## Options

- Require a cycling race before any cycling target
- Let the LLM infer cycling pace, zones, or power from ordinary rides
- Use athlete-confirmed Garmin heart-rate zones for bounded endurance targets
  while keeping harder intensity behind an explicit benchmark

## Chosen

Pace stores a manually confirmed local copy of the five Garmin cycling
heart-rate zones. It never estimates these zones from observed maximum heart
rate or ordinary activity data. When the 28-day planning gate is ready, two
ride activities exist in the last 14 days, and the profile is saved, Python
permits a plan draft to use cycling distance, duration, and Garmin zone 1–5.

The zone number is a structured field, not prose. Python requires 70–90% of
planned cycling time in Z2/Z3 and permits no more than 10% in Z4/Z5. It writes
the corresponding local BPM range itself. Cycling pace is never permitted.
Cycling power remains blocked until the athlete explicitly completes and marks
the existing `ride_20min_power_test`.

## Reason

This gives cycling a practical endurance target that matches the athlete's
actual use of the sport, without pretending that a race result or a guessed
power number exists. Keeping the zone number structured makes the boundary
enforceable even when an LLM drafts the surrounding session language.

## Consequences

- Garmin zones must be entered once with `pace zones set`; missing zones leave
  cycling plans at RPE/no-target only.
- Two recent rides are a continuity requirement, not permission for unlimited
  cycling volume.
- A future owner decision is required before changing the 70–90% Z2/Z3 or 10%
  Z4/Z5 distribution rule, or changing the power-test rule.

---

# Decision #33

**Status: superseded in part by Decision #34.** The availability and sport-role
profile remains; Python no longer imposes a fixed weekly running frequency.

## Problem

`ride_primary` describes the preferred sport but does not decide how much
running belongs in a general plan. The first draft therefore made an unreviewed
assumption about running frequency, and it also omitted the agreed cycling
distance target.

## Options

- Let the LLM infer the number of weekly runs from sparse history
- Hard-code a run/cycle ratio for every athlete
- Store an athlete-selected weekly run-session count and validate the plan
  against it in Python

## Chosen

The athlete selects `weekly_run_sessions` from 0 to 7 as part of local planning
preferences. Pace validates the exact count in every seven-day detailed plan
window. The current athlete selection is two runs per week. The LLM may decide
the conservative content of those sessions only within existing evidence gates.

Every cycling session must now contain a distance and a permitted Garmin
heart-rate-zone target. A duration may supplement that target but cannot
replace distance.

## Reason

Frequency and sport mix are athlete intent, not facts a model should invent
from incomplete recent history. Storing the choice makes future drafts and
revisions explainable and repeatable. Requiring a structured distance protects
the previously agreed cycling session contract.

## Consequences

- Existing saved preferences require one explicit update before a new draft.
- A draft that misses the selected run frequency or a cycling distance is
  rejected before it reaches the local database.
- Changing running frequency later is an explicit preference update, not an AI
  adjustment after feedback.

---

# Decision #34

## Problem

Pace had started to turn provisional coaching heuristics into Python rules:
an exact weekly run count and a fixed cycling-zone distribution. Those are not
athlete facts or technical safety boundaries. They are coaching choices that
need to respond to actual training history, recovery, goals, and uncertainty.

## Options

- Keep numerical coaching heuristics as Python validation rules
- Let an unstructured chatbot make plans without factual boundaries
- Keep Python responsible for verified facts and explicit athlete constraints,
  while a reviewable coach model makes training decisions over those facts

## Chosen

The athlete provides intent — such as `ride_primary`, availability, race
priority, and taper preference. The coach model decides session mix, running
frequency, cycling-zone distribution, progression, and individual session
content from the selected Pace facts. Its conclusion is stored separately as a
`coach_assessment` containing observed facts, inferences, rationale,
uncertainties, and named general coaching principles.

Python continues to enforce data integrity and explicit boundaries: factual
Garmin inputs, active planning blockers, date ranges, reviewable draft status,
run pace and cycling power eligibility, known Garmin zone boundaries, no
cycling pace, and no automatic acceptance or overwrite. A cycling plan session
must still specify purpose, distance, duration, and a valid configured zone;
these are output-completeness checks rather than a prescribed training policy.

Pace does not yet have a source-attributed coaching knowledge library. The
coach model's general principles must therefore be labelled as such, never as
citations or verified research. Batch K1 will add reviewed sources and an
evidence-selection contract before source-based claims are shown.

## Reason

This makes Pace a data-grounded coach rather than a set of rigid training
templates, while preserving the limits that prevent data fabrication, unsafe
automatic changes, and invented performance targets. Separating facts from
inferences makes the model's reasoning inspectable and correctable by the
athlete.

## Consequences

- The temporary Python rules for exactly two weekly runs and a 70–90% Z2/Z3
  distribution are removed.
- `ride_primary` informs a coaching decision; it is not a fixed run/ride ratio.
- New plan drafts display their coach assessment in the existing CLI JSON.
- K1 must establish curated, source-attributed knowledge before Pace claims
  that any training recommendation is research-cited.

---

# Decision #35

## Problem

An independent J3 review found that the first draft contract still allowed
important ambiguity: pace and power could be represented as free target text,
coach assessments could be incomplete, revision drafts did not formally reuse
their parent's block, availability was not enforced locally, and legacy plan
rows could look equivalent to a current plan. It also identified technical
integrity gaps around stale Garmin history, SQLite foreign keys, and the
superseded weekly-run preference column.

## Options

- Keep the original J3 JSON shape and compensate with stronger prompt wording
- Replace all historical plans with a new schema
- Introduce a versioned, structured plan contract and reject legacy or
  incomplete plans at the actions that would make them authoritative

## Chosen

Pace uses plan-contract version 2 for every new draft. A session has a
structured cycling `heart_rate_zone` and a separate structured primary target:
RPE, verified running pace, verified cycling power, or none. Python renders
display text itself. Pace and power must cite an eligible same-sport evidence
reference supplied by the local performance-readiness fact; power additionally
requires the existing 20-minute cycling power-test protocol. A cycling session
may combine its required zone with power. Cycling pace remains forbidden.

Every current coach assessment must contain at least one ID from the selected
fact catalog as well as non-empty inference, rationale, uncertainty, and
general-principle fields. The catalog records each selected value with
provenance and is the sole source of facts available to the model. It excludes
raw Garmin data, private context-note text, and unbounded local history.

Python validates each selected weekday and explicit per-day time cap, and the
initial block outline must cover the full block contiguously. A revision keeps
the accepted parent's block start, end, and outline; it changes only a new
seven- or fourteen-day detailed draft. When one revision is accepted, its
parent is superseded and all sibling revisions are stale. Plans created before
contract version 2 stay readable but cannot be accepted or revised.

Plan readiness blocks otherwise-contiguous Garmin history that is more than
one day old. SQLite foreign keys are enabled for every Pace connection and
`pace db init` runs `foreign_key_check` before an upgrade. The migration also
removes the obsolete `weekly_run_sessions` preference column rather than
leaving schema drift after Decision #34.

## Reason

The AI should make coaching judgments from factual constraints, but its output
must be impossible to reinterpret as unsupported performance evidence or as an
automatic plan change. A versioned contract permits that hardening without
silently rewriting the athlete's earlier plan history. Local validation keeps
explicit athlete constraints and database integrity outside the model's
control.

## Consequences

- Draft ID 1 and any other earlier J3 drafts require a fresh `pace plan draft`
  before acceptance or revision after the migration.
- The JSON shown by `pace plan show` now exposes a structured target and a
  provenance-backed coach assessment instead of trusting a free target string.
- Plan generation may be blocked until a current Garmin sync is available;
  this is intentional data-quality protection, not a coaching judgment.
- K1 remains necessary before Pace can call a coaching rationale research
  cited or evidence sourced.

---

# Decision #36

## Problem

The J3 plan contract became safe and reviewable, but its default CLI output is
large JSON. That is useful for inspection and testing, but unsuitable as the
main way an athlete reads a daily plan or considers the coach's reasoning.
Building a web application at this point would introduce a second UI runtime,
authentication and deployment decisions, and a larger privacy surface before
the underlying coaching workflow has been used.

## Options

- Keep JSON as the only plan presentation
- Build a server-backed dashboard or full web application now
- Add small local terminal and HTML views over the existing persisted plan
  contract

## Chosen

Batch J3.3 adds `pace plan today`, `pace plan review --id`, and `pace plan
report --id`. The first two are readable terminal views. The report command
creates a self-contained HTML file at `reports/plan-<id>.html`, which the
athlete opens directly in a browser.

The presentation layer is read-only: it reads a stored plan and never calls an
LLM, syncs Garmin, writes feedback, accepts a plan, or creates a revision. It
renders plan metadata, detailed sessions, feedback outcomes, block outline,
coach assessment, and labels for the selected fact categories. It deliberately
does not render raw Garmin payloads, the raw fact-catalog JSON, or any private
feedback/context-note text. `reports/` is ignored by Git, created owner-only,
and each HTML file is owner-only.

## Reason

This makes the existing coaching flow usable now while preserving the
local-first privacy model and avoiding premature web-product architecture. The
HTML document is a disposable derived view, not another source of truth or a
second data model. A later interactive dashboard can reuse the same plan facts
and presentation rules.

## Consequences

- JSON remains available through `pace plan show` for debugging and machine
  inspection; the human default is `pace plan review` or the HTML report.
- No database migration, browser automation, web server, or external asset is
  needed for J3.3.
- A future Batch L may add an interactive local dashboard, but it must consume
  the persisted plan contract rather than reimplement planning or coaching
  decisions in the UI.

---

# Decision #37

## Problem

The default LLM voice can turn an otherwise factual plan into generic,
overly-soft wellness language. Statements such as routine referrals to a care
provider for normal fatigue or an ordinary hard day do not make the plan safer
or more useful; they weaken the coach's concrete accountability.

## Options

- Keep the provider's default helpful-assistant tone
- Make Pace aggressively motivational and dismiss risk or uncertainty
- Use a direct, factual endurance-coach tone while retaining the existing
  factual and medical boundaries

## Chosen

Pace prompts require a direct, unsentimental Swedish coach voice. The model
states what the local facts support, what they do not support, and the next
action. It avoids praise, soothing, therapy language, generic wellness text,
and routine care-provider referrals for ordinary fatigue, poor sleep, or
discomfort.

Directness is not permission for recklessness. Pace remains non-diagnostic and
does not give medical advice. Where the selected facts justify reducing or
skipping a session, it says so plainly and does not compensate by adding
intensity later.

## Reason

The athlete wants a coach that holds the plan to the evidence, not a chatbot
that pads every conclusion with reassurance. Clear language makes uncertainty,
training constraints, and decisions easier to act on.

## Consequences

- Existing stored plans preserve their historical wording; newly generated
  drafts and Pace AI answers use the new tone instruction.
- A future coaching-knowledge library may improve the substance of advice, but
  it must preserve this tone and the boundary between facts, inferences, and
  medical assessment.

---

# Decision #38

## Problem

Pace could express coaching rationale, but that rationale had no constrained,
inspectable research support. Letting the model search the web or rely on
unbounded background knowledge would make sources, freshness, privacy, and
review impossible to control.

## Options

- Let each AI call search the web or retrieve raw papers
- Add embeddings and a vector database before there is a substantial library
- Keep a small, checked-in library of human-reviewed evidence briefs and select
  them deterministically

## Chosen

K1 adds `knowledge/sources.json` and reviewed Markdown briefs. Each brief has
an ID, source IDs, supported claims, limitations, and applicability. At runtime
Pace reads only those local files. Python selects at most three relevant briefs
from question text or the selected plan facts, then sends only that compact
contract to the model.

The model must return `knowledge_references`; Python rejects a reference not
included in that specific request. New plan drafts must cite at least one
selected brief. `pace knowledge list` and `pace knowledge show --id <brief>`
make the exact local claims, limits, and source links readable. Plan review and
the private HTML report show the cited brief titles.

## Reason

This gives Pace evidence traceability without pretending that a handful of
papers is a complete coaching database. It keeps data minimization intact,
makes curation reviewable in Git, and preserves the separation between local
athlete facts, model inferences, and research support.

## Consequences

- There is no runtime internet access, raw-paper copying, automatic knowledge
  ingestion, embeddings, or vector database in K1.
- Briefs do not override athlete facts, preferences, Python eligibility gates,
  or safety boundaries; they constrain how the model may justify an inference.
- Adding or changing a brief is a reviewed repository change, including its
  source metadata and explicit limitations.

---

# Decision #39

## Problem

An athlete needs to ask a practical same-day question — for example whether a
planned run can be replaced by a ride — without turning a conversational model
into an unbounded writer of the training plan or retaining a private chat log.

## Options

- Keep only a one-shot factual `pace ask` command
- Persist an open-ended chat history and let the model edit the accepted plan
- Add a bounded plan-aware dialogue that returns only validated, unsaved
  adjustment drafts

## Chosen

K2 adds `pace coach ask --plan-id <id> "question"` and `pace coach chat
--plan-id <id>`. Both require one accepted plan that is active on the selected
date. Each turn rebuilds current local facts and sends only the accepted plan,
selected facts, selected knowledge briefs, and at most four earlier
in-memory dialogue turns. The process discards that history on exit; requests
remain provider-stateless with `store=False`.

The model can return a same-day `keep_plan`, `skip`, or `replace` draft.
Python verifies that any referenced session belongs to the plan and selected
date. A replacement also has to pass availability, sport, Garmin zone, and
pace/power-evidence checks. No response writes data, changes a session,
accepts a plan, or creates a revision. The existing revision flow remains the
only route to a durable plan version.

## Reason

This gives the athlete an actual coach conversation for day-to-day trade-offs
while keeping plan authority, facts, privacy boundaries, and persistent state
outside the model. The output is useful immediately but cannot silently become
training history or a new authoritative schedule.

## Consequences

- K2 does not yet apply an exact dialogue proposal as a stored revision; that
  needs a separate, reviewable adjustment-acceptance design.
- Coaching ambition (Försiktig/Balanserad/Offensiv) remains a new shared
  product decision rather than an implicit prompt preference.
- The active chat's selected messages are sent again with the next turn, so
  the athlete should not put private text into the dialogue that they would
  not want in that explicit AI request.

---

# Decision #40

## Problem

The athlete may explicitly want a more cautious or more ambitious training
approach. Treating that wish as a direct intensity/volume command would
contradict Pace's factual planning model; ignoring it would make the coach
unresponsive to legitimate athlete intent.

## Options

- Hard-code numerical progression or intensity rules for each ambition level
- Ignore athlete ambition and always use one hidden model default
- Store ambition as explicit intent and let the coach model apply it only
  within the already selected facts and Python boundaries

## Chosen

Pace stores `cautious`, `balanced`, or `ambitious` on the single local training
preference profile. Existing athletes receive `balanced` through a database
migration. `pace preferences ambition --ambition <level>` changes just this
preference without resetting sport role or availability.

The preference is sent to both plan drafting and coach dialogue. It may shape
the model's proposed margin, progression, volume, or quality only when local
facts support that choice. The model must explain its effect in the coaching
assessment or explain why the facts prevent a more assertive proposal. Python
does not translate the label into a percentage, session count, zone ratio, or
any weakened gate.

## Reason

This keeps athlete intent visible without allowing desire to masquerade as
capacity or override recovery, continuity, availability, evidence, or explicit
plan acceptance.

## Consequences

- A new plan draft can be more or less assertive for the same factual profile,
  but the decision remains reviewable rather than hidden in a fixed formula.
- `ambitious` is not permission to add arbitrary hard training or bypass a
  reduction/skip recommendation.
- Future personalisation may learn how the athlete responds to each level, but
  it must not retroactively reinterpret the stored preference as performance
  evidence.

---

# Decision #41

## Problem

An athlete must be able to correct a mistaken future race date or remove a
race that was entered by mistake. Once a plan or Garmin result points at that
race, however, altering or deleting it would silently change the meaning of
stored history.

## Options

- Let any race be edited or deleted at any time
- Make every race permanently immutable after creation
- Allow changes while a future race is unused, then preserve referenced races
  and provide a non-destructive cancellation state

## Chosen

An unused future race can have its facts corrected or be deleted. A race with
any plan or Garmin evidence reference cannot have its facts changed or be
deleted. `cancelled` is a retained local state: it disappears from upcoming
race selection and cannot be used for a new plan or Garmin evidence link.

Cancellation is allowed for an unused or draft-plan-only future race. It is
blocked once an accepted plan or Garmin race evidence uses the race. This
avoids silently changing an active coaching commitment or historical result.

## Reason

The athlete can fix ordinary entry mistakes without turning the race table into
mutable history. The restriction is deliberately based on real local
references, not a model interpretation of whether a race still matters.

## Consequences

- To correct a referenced race, add a new race and create the appropriate new
  plan rather than rewriting the original record.
- Draft plans that refer to a cancelled race remain readable but cannot be
  accepted; a newly generated draft will use only active races.
- Cancelled races remain available through an explicit audit list, so an
  accidental cancellation is visible rather than silently erased.

---

# Decision #42

## Problem

Pace started as one developer's local project. A private invited friend needs a
safe, predictable first run without access to the developer's secret-file
layout or a need to export an API key in every terminal session.

## Options

- Keep the developer-specific sibling secrets path as the default
- Require every user to export `OPENAI_API_KEY` before each AI command
- Read one owner-only, Git-ignored key file inside each local Pace clone while
  preserving environment variables as an explicit override

## Chosen

Pace's default optional AI-key file is `.local/pace.env` inside the cloned
repository. It contains only `OPENAI_API_KEY`, must have owner-only permissions,
and is ignored by Git. `OPENAI_API_KEY` in the environment still takes
precedence and `PACE_OPENAI_SECRETS_FILE` can explicitly select another file.

Release Batch L0 prepares a private, invited-friend alpha: a simple README,
an MIT license, and a GitHub Actions workflow that runs the locked dependency
install, Ruff, and tests on pushes to `main` and pull requests.

## Reason

This gives each athlete their own key and local data by default without
pretending that Pace is a hosted product. The release guard catches ordinary
regressions before a collaborator merges them, while the private repository
and explicit invitation remain the access boundary.

## Consequences

- Each friend pays for and controls their own OpenAI key; Pace never shares
  the owner's key through the repository.
- The default is convenient for a local clone, not a global multi-machine
  secrets manager.
- GitHub Actions validates code only. It does not run Garmin login, sync, or
  live OpenAI calls, and it never receives local athlete data or secrets.
- MIT permits use and modification without warranty. Repository write access
  must still remain limited to trusted collaborators.

---

# Decision #43

## Problem

Pace needs to learn from an athlete's completed, limited, and skipped plan
sessions without treating silence as failure, exposing private free text, or
letting a trend automatically rewrite a plan.

## Options

- Infer every planned-but-unreported session as skipped
- Save free-text coaching diaries and let the model interpret them directly
- Store optional structured RPE and reason codes, then derive bounded local
  trend facts only from explicit feedback

## Chosen

`pace plan feedback` accepts optional RPE 1–10 for `completed` and
`completed_limited`, plus an optional reason (`schedule`, `fatigue`, `pain`,
`illness`, `travel`, or `other`) for `completed_limited` and `skipped`.

Pace calculates two fixed 28-day windows locally from those explicit records.
Six recent feedback records are required before the current window is ready;
four prior records are required for a window-to-window comparison. The result
reports its data counts and the permanent limitation
`explicit_feedback_only`: it cannot say anything about unreported sessions or
prove why an outcome or RPE changed.

The aggregate, text-free trend fact is available to `pace trends show`, new
plan drafts, revision drafts, and plan-aware coach dialogue. It never creates
a context event, diagnoses a condition, changes a plan automatically, or sends
the athlete's private feedback note to the model.

## Reason

This turns actual athlete feedback into useful personalisation evidence while
preserving the distinction between observation, unknown data, and coaching
judgment. The athlete remains in control of every durable plan change.

## Consequences

- Feedback is optional, so an empty trend profile is normal and explicitly
  limited rather than silently pessimistic.
- Reason codes are deliberately small and structured; richer narratives stay
  in the local note and are shared with a revision only by the existing
  per-note opt-in.
- Future personalisation can build on this contract, but may not reinterpret
  it as a causal, medical, or automatic workload system without a new decision.

---

# Decision #44

## Chosen

L2 is a dense owner-only local HTML/SVG dashboard over existing facts. It is
read-only and has no server, external assets, AI call, raw payload, or private
note text. L3 uses a fresh 56-day explicit-feedback evidence gate (12 records
overall; four for same-sport observations). An athlete may explicitly accept a
plan-derived coaching principle; it is sent only while active and becomes due
for review after 84 days. Neither layer changes a plan automatically.

## Reason

The dashboard improves daily usability without becoming a second source of
truth. Explicit acceptance preserves continuity without storing opaque model
opinions as athlete facts.

---

# Decision #45

## Chosen

M1 creates a weekly review only when the athlete explicitly runs `pace review
weekly`. Python assembles compact facts and selected local knowledge first; a
stateless AI call with `store=False` returns validated Swedish review sections.
Pace writes only an owner-only local HTML report. The review cannot write or
accept a plan, feedback, or context event.

## Reason

This provides a useful coach-level synthesis without turning normal syncs into
AI jobs or allowing a narrative review to become an automatic plan change.

---

# Decision #46

## Problem

The curated local knowledge library is intentionally small. Treating it as a
hard allowlist for all model reasoning makes the coach less useful and can
discard an otherwise valid answer merely because it uses general training
knowledge.

## Options

- Restrict every AI conclusion to selected local knowledge briefs
- Allow unconstrained model claims about athlete data
- Keep athlete facts constrained to Pace while allowing labelled general coach
  reasoning

## Chosen

Pace facts are the complete factual contract about the athlete. The model may
apply general endurance-coaching knowledge for a separate coach assessment and
recommendations. Curated local briefs are optional, source-attributed support;
they are not a complete allowlist. Only selected local brief IDs are retained
as citations.

## Reason

Python and Pace data are the reliable source for numerical facts, dates,
history, data quality, and target eligibility. A capable coaching model should
still use its general domain knowledge to choose a sensible interpretation,
session purpose, and recommendation from those facts. Separating the two makes
the reasoning more useful without making model opinion look like athlete data
or research evidence.

## Consequences

- Unknown or invented local knowledge references cannot discard an otherwise
  valid answer; Pace removes them rather than displaying them as sources.
- Weekly reviews show Pace facts and coach assessments as separate sections.
- Plan drafts and dialogue retain all deterministic availability, target,
  data-quality, draft, and acceptance gates.
- General model knowledge must not be presented as a study, external citation,
  diagnosis, or a fact about the athlete.

---

# Decision #47

## Problem

Plans could previously describe a session only as purpose, duration/distance,
and one overall target. That cannot represent an executable workout such as
10 × 1 km with recovery, and it gave neither the athlete nor a future revision
enough structure to judge what was attempted.

## Options

- Keep free-text pass descriptions
- Create a separate relational table for workout blocks
- Store a validated structured workout snapshot on each immutable plan session

## Chosen

New plan contract v3 stores ordered `workout_steps` JSON on every planned
session. A step is warmup, steady work, interval, or cooldown. A continuous
easy or endurance session normally consists of one `steady` block; warmup and
cooldown are optional tools, not mandatory ceremony. Intervals carry
their repetitions, work dose, recovery dose, work target, and recovery target.
The exact same Python target-evidence gates validate every work and recovery
target as validate the session overall. Existing v2 plans remain readable as
history but must be regenerated before revision.

`pace plan workout evaluate --session-id` is read-only. It shows the stored
steps, explicit feedback, and same-day same-sport Garmin candidates. It never
marks a session completed, derives interval compliance, changes feedback, or
rewrites a plan.

## Reason

Plans are immutable version snapshots already. Embedded validated JSON keeps a
workout together with the accepted plan version, avoids a premature table and
join model, and is sufficient while Pace does not yet ingest interval-level
Garmin data. Explicit athlete feedback remains the durable outcome source.

## Consequences

- New plans can express genuine quality sessions with visible work and recovery.
- A Garmin activity match is deliberately not treated as evidence that every
  prescribed interval occurred.
- If Pace later needs interval-level compliance analytics, a normalized workout
  block table can be introduced by a new migration and decision.

---

# Decision #48

## Chosen

K1.1 broadens the checked-in reviewed knowledge library from five to fifty
briefs across structured
workouts, cycling, strength, HRV, sleep, recovery, pacing, taper, and
run/cycle transfer. Python selects at most five relevant briefs, still with no
runtime web search, embeddings, vector database, raw-paper storage, or
automatic ingestion. Briefs remain optional support under Decision #46.

## Reason

The original library was useful but too narrow to provide transparent local
support across the kinds of decisions Pace now makes. More reviewed source
summaries improve coverage without pretending that a finite catalog replaces a
coaching model's general knowledge.

## Consequences

- The library is more useful as an inspectable reference, but it remains
  versioned content that needs human review when expanded.
- Athlete-specific facts, data quality, and deterministic Python gates retain
  priority over every brief.

---

# Decision #49

## Problem

Pace can create structured short plans, but a usable feedback loop also needs
to know when another explicit revision is due, compare prescribed work with
available Garmin detail, learn only defensible patterns from repeated feedback,
and present the current state without forcing the athlete to read several JSON
documents. These additions must not turn Pace into an autonomous plan writer or
hide its reasoning inside a proprietary score.

## Options

- Regenerate and accept a plan automatically after every sync
- Rotate fixed workout templates and infer completion from Garmin
- Keep planning model-led but bounded by deterministic facts, explicit
  feedback, visible comparisons, and athlete acceptance

## Chosen

Pace adds a read-only rolling checkpoint. It recommends a new draft or bounded
revision when the detailed window ends or a race approaches, but never creates
or accepts one. The coach model owns workout form from the selected facts and
block purpose; Python does not rotate templates. An active race inside the
detailed window must appear as a same-date, same-sport session and retains its
stored A/B/C role.

Workout evaluation includes privacy-minimized Garmin detail and splits plus
planned-versus-observed duration and distance. These are comparison facts only:
splits do not prove interval compliance and explicit athlete feedback remains
the durable outcome.

Personalisation emits non-causal observations only after the existing 56-day
thresholds: 12 explicit feedback records overall and four for a same-sport
observation. Missing feedback remains unknown.

`pace home` is a static owner-only entry page over the dashboard, active plan,
weekly review, races, checkpoint, and personalisation. `pace analysis show`
exposes 28-day duration, known distance, frequency, explicit feedback/RPE, and
recovery coverage. Pace does not create a proprietary training-load score.

Six synthetic coach scenarios run through a fake generator in the normal test
suite. Real-model evaluation is an explicit six-call command over synthetic
facts only and never runs in CI. Garmin workout export remains deferred.

## Reason

This closes the practical plan-feedback-revision loop while preserving the
system's strongest boundaries: code calculates inspectable facts, the model
makes coaching judgments, and the athlete controls every durable plan change.
The evaluation path detects contract regressions without exposing personal data
or making routine tests depend on a paid external service.

## Consequences

- `pace home` may regenerate local reports, but it never syncs, calls AI, or
  mutates application data.
- A checkpoint is guidance, not an autonomous scheduler.
- Different model calls may still make different coaching judgments; accepted
  plans and stored assessments remain immutable reviewable snapshots.
- Personalisation can describe repeated explicit outcomes but cannot claim why
  they occurred.
- Device workout export, automated acceptance, causal inference, and opaque
  training-load formulas require separate future decisions.

---

# Current Core Decisions Summary

| Area | Decision |
|---|---|
| Language | Python |
| Package management | uv |
| Data source | Garmin only |
| Database | SQLite |
| Interface | CLI plus owner-only local static HTML |
| Architecture style | Layered application |
| Metrics | Deterministic Python |
| Memory | Structured context events |
| AI | Explicit, stateless, read-only `pace ask` over selected facts |
| Product | Persistent coach |
| Deployment | Local-first |
| Athlete timezone | Europe/Stockholm |
| Included sports | Run and ride only |
| Sync batch | Maximum seven days, repeatable by end date |
| Recovery merge | Latest successful snapshot per endpoint |
| Local privacy | Owner-only files; no application encryption |
| Provider deletions | Local append/update archive; no inferred deletes |
