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

### Batch J — Advanced coaching

Consider planning, workout generation, research retrieval, and adaptive
recommendations only after the earlier layers have stable contracts and
evidence-backed product decisions.

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
- Medical or clinical interpretation
