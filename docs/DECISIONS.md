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

# Current Core Decisions Summary

| Area | Decision |
|---|---|
| Language | Python |
| Package management | uv |
| Data source | Garmin only |
| Database | SQLite |
| Interface | CLI first |
| Architecture style | Layered application |
| Metrics | Deterministic Python |
| Memory | Structured context events |
| AI | Later reasoning layer |
| Product | Persistent coach |
| Deployment | Local-first |
