# Pace — Architecture

## Architectural goal

Pace is a local, layered Python application for one athlete. External data
collection, persistence, deterministic analysis, coaching judgment, and user
presentation must remain separate so that each can be tested and reviewed.

The application is not a generic autonomous agent and not an internet-facing
web service.

## System overview

```text
                         explicit request
Garmin Connect ──> Garmin integration ──> normalization
                                              │
                                              v
                                      SQLite repositories
                                              │
                         ┌────────────────────┼───────────────────┐
                         v                    v                   v
                 deterministic facts   structured context   stored plans
                         │                    │                   │
                         └────────────────────┼───────────────────┘
                                              v
                                    application services
                                      │               │
                                      v               v
                              local web UI / CLI   selected fact catalog
                                                      │
                                               explicit AI request
                                                      │
                                                      v
                                                   OpenAI
                                                      │
                                              structured response
                                                      │
                                            Python validation + write
```

The arrows matter. Garmin code does not coach, repositories do not calculate
metrics, the model does not query the database, and the web layer does not own
training rules.

## Layer responsibilities

### Configuration

`pace.config` resolves project paths, local secrets, model choice, time zone,
and database settings. The athlete calendar currently uses
`Europe/Stockholm`; activity instants are stored in UTC.

### Garmin integration

`pace.integrations.garmin` wraps the community `garminconnect` library behind a
small Pace-owned interface. It handles authentication, MFA, reusable tokens,
bounded API calls, and provider-specific errors.

Provider dictionaries are normalized before they reach business logic:

```text
Garmin dictionary
    -> validation and unit conversion
    -> Pace normalized model
    -> repository upsert
```

Only explicit Garmin requests contact the provider. Ordinary reads, dashboards,
and tests use local data.

### Persistence and repositories

SQLite is the local system of record. SQLAlchemy defines storage models;
Alembic owns forward-only schema migrations. Repository classes own queries,
upserts, and database-specific behavior.

Important stored concepts include:

- activities and privacy-minimized performance detail;
- daily recovery metrics;
- context events;
- synchronization audit records;
- races and verified performance evidence;
- athlete preferences and cycling heart-rate zones;
- immutable training-plan versions, structured sessions, workout steps, and
  explicit feedback;
- athlete-confirmed coaching principles.

Key identities remain deterministic, including
`UNIQUE(provider, provider_activity_id)` for activities and one daily metric
row per date. Foreign keys are enabled for every SQLite connection.

Repositories do not interpret recovery, generate prose, or call Garmin or an
LLM.

### Deterministic analysis

`pace.analysis`, `pace.capacity`, `pace.trends`, `pace.rules`, and their
services calculate facts from normalized rows. These layers own date windows,
training totals, continuity, recovery baselines, data coverage, and transparent
rule outcomes.

Pace deliberately does not hide the inputs behind a proprietary training-load
score. Missing distance is `null`, not zero. Unsupported activities are not
counted as run or ride.

### Application services

`pace.services` is the workflow boundary. Services coordinate repositories,
deterministic analysis, integrations, and optional model clients. Both the CLI
and web app call these services so there is one implementation of each
operation.

Representative services:

- `GarminSyncService` — the only Garmin activity/recovery write path;
- `AthleteStateService` — a compact dated view of facts and context;
- `TransparentTrainingAnalysisService` — multi-horizon training evidence;
- `TrainingPlanService` — plan generation, validation, versioning, feedback,
  and revisions;
- `CoachDialogueService` — bounded plan-aware conversation and unsaved action
  proposals;
- `DashboardService` and `WeeklyReviewService` — read models and explicit
  review generation.

### AI clients and contracts

OpenAI clients receive a deliberately selected fact catalog, not direct
database access or raw provider data. Separate structured contracts exist for
questions, dialogue, plan generation, and weekly review.

Appropriate model work:

- coaching interpretation and explanation;
- session and block design;
- proposing structured context or feedback from natural language;
- weekly synthesis;
- choosing relevant coaching principles.

Inappropriate model work:

- metric calculation;
- credential handling;
- SQL or repository access;
- unbounded raw-history ingestion;
- silent persistent writes;
- medical diagnosis;
- claiming unsupported athlete facts.

The local knowledge library provides versioned, source-linked coaching support.
It helps trace principles but does not prevent the model from applying general
endurance knowledge. Any statement about this athlete must still be grounded in
the selected Pace facts.

### Presentation

The primary interface is a React/TypeScript single-page application generated
as static assets under `src/pace/web/frontend_dist`. FastAPI serves those assets
and a normalized same-origin `/api/v1/*` presentation API. Editable source
lives under `frontend/`; end users do not need Node.js. The previous
server-rendered onboarding remains available as the hardened local setup
fallback while React feature parity is completed.

`pace serve` binds Uvicorn to `127.0.0.1` only. Accepted host names are
restricted, state-changing requests require the same session CSRF token in both
frontends, and responses add restrictive browser headers.

The web layer may compose read models and call services. It must not contain
training calculations, arbitrary file access, arbitrary command execution, raw
provider payloads, or credentials. Coach conversation is bounded process
memory and disappears when the server stops. React talks only to the same
origin through `HttpPaceClient`; synthetic fixtures are used solely when the
frontend is explicitly built with `VITE_PACE_USE_MOCKS=true`.

The CLI remains a supported adapter for diagnostics and advanced reproducible
workflows. It may parse arguments, call services, format results, and return
useful exit codes; it must not contain SQL, Garmin normalization, or coaching
rules.

## Main data flows

### Garmin synchronization

```text
explicit UI/CLI request
    -> maximum seven-day service batch
    -> authenticated Garmin client
    -> independent activity and recovery endpoint reads
    -> normalization
    -> endpoint-aware merge and idempotent upsert
    -> sync audit result
    -> refreshed local read models
```

An 80-day import is a sequence of bounded batches, not one oversized provider
request. Authentication or rate limiting stops the remaining range while
preserving batches already completed.

### Plan generation and revision

```text
explicit athlete goal selection
    + current preferences and constraints
    + multi-horizon history and recovery facts
    + selected race and knowledge support
    -> structured model request
    -> complete structured plan response
    -> Python validation
    -> accepted plan OR inactive race-volume exception awaiting approval
    -> previous overlapping version superseded only after activation
```

The explicit create or revise action is normally the authorization. General
plans that cross athlete-defined weekly base ceilings fail validation. A
race-directed plan may instead be stored as `volume_exception_pending`; a
separate approval is then required and the active plan remains unchanged until
approval. If ordinary generation or validation fails, no partial plan is stored.

Plans describe a longer block direction while detailing only 7–14 days.
Checkpoint logic can recommend another explicit revision as the detailed window
ends; it cannot invoke the model automatically.

Coach dialogue receives the active plan as the current prescription plus a
bounded plan-lineage window covering 28 days before and 14 days after the
conversation date, from at most six ancestor revisions of the same plan. This lets it answer
questions about sessions that disappeared when a version was superseded.
An omission is not an explicit cancellation because the current schema has no
such fact. A deterministic effective schedule overlays the lineage: the newest
revision wins for dates it specifies and otherwise inherits the nearest ancestor
session. Earlier revision entries prove only what Pace prescribed; Garmin
activity facts and explicit athlete feedback remain the evidence of completion.
An inherited session remains a valid feedback target unless a newer revision
contains a replacement on the same date.

An early revision is an extension, not a rewrite of current days. The model's
writable range begins after the accepted detailed window. The new immutable
version carries forward uncompleted current sessions unchanged, appends the
validated generated sessions, and only then supersedes its parent.

### Dialogue and feedback

```text
athlete message
    + active plan
    + bounded normalized history
    + current deterministic facts
    -> model response
    -> optional unsaved proposal card
    -> athlete confirmation
    -> service validation and persistence
```

Dialogue can propose context, feedback, or a same-day adjustment. It cannot
replace a plan directly. Explicit feedback is the durable statement of whether
a session was completed; Garmin activity matching is supporting evidence, not
an automatic claim of compliance.

### Weekly review

A weekly review is an explicit, dated AI snapshot. The generated result is
stored locally and rendered unchanged later so an old week does not receive a
different retrospective story each time it is opened.

## Failure and integrity behavior

- Sync is idempotent. Repeating identical data reports zero changes.
- Recovery endpoints merge independently; one unavailable endpoint cannot
  erase valid values from another or from an earlier sync.
- Malformed provider data becomes a partial result or explicit error rather
  than an invented zero.
- Plan writes are atomic and versioned.
- SQLite files and containing directories receive owner-only permissions.
- Local Garmin deletion is not inferred from absence in a later response;
  v0.1 is an append/update archive.
- Default tests cannot contact Garmin or OpenAI.

## Package map

```text
src/pace/
├── integrations/garmin/   provider boundary and normalization
├── database/              engine, sessions, models, initialization
├── repositories/          persistence operations
├── analysis/              deterministic training and recovery metrics
├── capacity/              historical capacity evidence
├── trends/                explicit multi-period trends
├── rules/                 transparent rule evaluations
├── state/                 athlete-state contracts
├── performance/           verified result and benchmark contracts
├── planning/              plan and checkpoint contracts
├── workouts/              structured workout-step contracts
├── personalization/       explicit feedback-derived evidence
├── knowledge/             reviewed coaching references and selection
├── ai/                    general question and plan clients
├── coach/                 dialogue client contracts
├── weekly_review/         weekly-review model contracts
├── services/              application workflows
├── presentation/          reusable report rendering
├── web/                   loopback HTTP adapter and UI assets
└── cli/                   command-line adapter
```

The large `TrainingPlanService`, web router, and CLI adapter are current
maintenance hotspots. They should be split only through behavior-preserving,
tested refactors, not during unrelated feature work.

## Security boundary

Sensitive local paths are Git-ignored and owner-only where Pace creates them.
Garmin passwords are never persisted by Pace. Reusable session tokens and the
OpenAI key must not be logged or returned to the browser.

Loopback binding, host validation, CSRF, content-security policy, and related
headers reduce local browser risk. They do not make the application safe to
bind to `0.0.0.0` or publish behind a public URL. Hosted or multi-user operation
requires a new identity, authorization, secret-management, isolation, and data
retention design.

## Test strategy

The default quality gate is:

```text
Ruff
    +
synthetic pytest suite
    +
blank-database Alembic upgrade
    +
CLI and local-web smoke checks
    +
secret and dependency review before release
```

Garmin fixtures and coaching scenarios must be synthetic. Live Garmin tests and
live model evaluations are always explicit, separate operations and must never
run in CI with personal credentials.
