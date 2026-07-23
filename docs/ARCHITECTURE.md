# Pace — Architecture

## Architectural Goal

Pace should begin as a small, local Python system.

The architecture should separate:

- external data collection
- data persistence
- numerical calculations
- athlete context
- athlete state
- interpretation rules
- natural-language explanation

Each layer should have a clear responsibility.

Coaching logic must not be hidden inside the Garmin integration or database layer.

---

## High-Level Architecture

```text
Garmin Connect
      |
      v
Garmin Integration
      |
      v
Normalization and Validation
      |
      v
SQLite Database
      |
      +--------------------+
      |                    |
      v                    v
Deterministic Metrics   Context Memory
      |                    |
      +---------+----------+
                |
                v
         Athlete State
                |
                v
           Rule Engine
                |
                v
      Explanation Engine
                |
                v
        AI Coach — later
                |
                v
               CLI
```

The initial system should work through the CLI without an AI model.

---

## Core Data Flow

### Garmin synchronization

```text
Garmin Connect
    ->
authenticated Garmin client
    ->
provider payloads
    ->
normalization
    ->
validation
    ->
database upsert
    ->
sync result
```

### Deterministic analysis

```text
activities + daily metrics
    ->
metric functions
    ->
structured metric results
    ->
athlete-state update
```

### Context-aware interpretation

```text
metric result
    +
relevant context events
    +
current athlete state
    ->
rule evaluation
    ->
structured explanation
```

### Future AI flow

```text
current question
    +
compact metric summary
    +
relevant activities
    +
relevant context events
    +
athlete state
    +
rule-engine output
    ->
LLM
    ->
coaching explanation
```

The LLM should not receive the complete raw Garmin history by default.

---

# Layers

## 1. Garmin Integration Layer

### Responsibilities

- authenticate with Garmin Connect
- reuse stored session tokens
- fetch activities
- fetch daily health and recovery data
- handle date ranges
- return provider payloads
- handle endpoint-specific failures
- respect rate limits
- produce clear integration errors

### Initial library

Use:

```text
python-garminconnect
```

The exact dependency may change later if maintenance or compatibility becomes a problem.

### Authentication

The local application may use the user's normal Garmin Connect credentials during login.

The Garmin password must not be:

- stored in SQLite
- committed to Git
- printed
- written to normal logs
- sent to an AI model

Stored Garmin session tokens should be reused to avoid repeated login attempts.

Suggested token path:

```text
.local/garmin_tokens/
```

The path must be ignored by Git.

### Rate limiting

Garmin may return HTTP 429 or other temporary failures.

The integration must:

- avoid aggressive retries
- reuse valid tokens
- use bounded backoff
- stop after a small retry limit
- report the failure clearly
- allow partial synchronization when appropriate

### Non-responsibilities

The Garmin integration must not:

- calculate coaching metrics
- infer fatigue
- generate recommendations
- store context events
- call an LLM
- contain user-interface formatting

---

## 2. Normalization and Validation Layer

Garmin payloads may use inconsistent names, missing values, and provider-specific structures.

This layer converts Garmin data into Pace's internal models.

### Responsibilities

- map Garmin sport types to internal sport types
- convert units
- parse timestamps and dates
- handle optional values
- validate required identifiers
- preserve the original raw payload
- create normalized records for persistence

### Internal sport examples

```text
run
ride
nordic_ski
alpine_ski
strength
rowing
other
```

Provider values should not be used directly throughout the application.

### Reason for normalization

Without normalization, Garmin-specific details leak into:

- metrics
- database queries
- rules
- tests
- future interfaces

Normalization creates a stable internal contract.

---

## 3. Persistence Layer

## Database choice

Use SQLite for version 1.

Suggested database path:

```text
data/pace.db
```

The path should be configurable.

SQLite is suitable because the first version is:

- local
- private
- single-user
- low-concurrency
- relatively small

SQLAlchemy may be used to keep database access explicit and testable.

### Core tables

#### `activities`

Stores normalized Garmin activities.

Suggested fields:

```text
id
provider
provider_activity_id
name
sport_type
start_time
duration_seconds
distance_meters
elevation_gain_meters
average_heart_rate
maximum_heart_rate
average_speed_mps
average_cadence
average_power
training_effect_aerobic
training_effect_anaerobic
raw_payload
created_at
updated_at
```

Constraints:

```text
UNIQUE(provider, provider_activity_id)
```

#### `daily_metrics`

Stores date-based Garmin recovery and health data.

Suggested fields:

```text
id
date
hrv_value
hrv_status
resting_heart_rate
sleep_duration_seconds
sleep_score
average_stress
body_battery_high
body_battery_low
training_readiness
recovery_time_hours
raw_payload
created_at
updated_at
```

Constraint:

```text
UNIQUE(date)
```

If multiple daily records are later needed, the uniqueness strategy can be revised.

#### `context_events`

Stores structured athlete explanations and life events.

Suggested fields:

```text
id
event_type
start_date
end_date
note
affected_metrics
severity
confidence
status
created_at
updated_at
```

Initial event types:

```text
social_event
alcohol
late_night
illness
injury
pain
travel
work_stress
poor_sleep
schedule_constraint
training_feedback
race
equipment_change
```

#### `sync_runs`

Stores synchronization history.

Suggested fields:

```text
id
provider
started_at
completed_at
status
requested_start_date
requested_end_date
activities_fetched
activities_inserted
activities_updated
daily_metrics_fetched
daily_metrics_inserted
daily_metrics_updated
error_summary
```

### Later tables

Possible later additions:

```text
athlete_state
training_goals
training_blocks
workout_plans
workout_steps
plan_versions
analysis_runs
coach_messages
coach_interpretations
```

Do not create these until their use cases are clear.

---

## 4. Repository Layer

Repositories isolate database operations from business logic.

Examples:

```text
ActivityRepository
DailyMetricRepository
ContextEventRepository
SyncRunRepository
```

### Responsibilities

- insert records
- update records
- perform upserts
- query date ranges
- query by sport
- retrieve relevant context events
- enforce database-specific operations

### Non-responsibilities

Repositories should not:

- calculate training metrics
- interpret HRV
- generate prose
- call Garmin
- contain CLI formatting

---

## 5. Service Layer

Services coordinate application workflows.

Examples:

```text
GarminSyncService
ActivityService
MetricService
ContextService
ExplanationService
```

### Example: Garmin sync service

```text
Garmin client
    ->
normalizer
    ->
repositories
    ->
sync-run record
```

The service decides how components are combined.

It should not contain low-level SQL or provider-specific parsing.

---

## 6. Deterministic Metrics Layer

This layer calculates numerical values in Python.

### Initial metrics

- activity count by sport
- weekly running distance
- weekly cycling duration
- total training duration
- longest run
- longest ride
- training frequency
- HRV rolling baseline
- HRV deviation from baseline
- resting heart-rate baseline
- resting heart-rate deviation
- recent sleep-duration trend
- low-HRV day detection

### Output format

Metric functions should return structured objects or typed models.

Example:

```python
HrvSummary(
    start_date=...,
    end_date=...,
    baseline_ms=...,
    current_value_ms=...,
    deviation_percent=...,
    below_baseline=True,
    confidence="medium",
)
```

Metric functions should not return coaching prose.

### Requirements

Metrics must be:

- deterministic
- tested
- independent of an LLM
- explicit about missing data
- explicit about calculation windows
- reproducible from stored records

---

## 7. Context Memory Layer

Context memory stores information that Garmin cannot observe.

Examples:

- illness
- pain
- alcohol
- social events
- travel
- work stress
- schedule restrictions
- athlete feedback
- explanation for poor sleep
- correction of a previous interpretation

### Temporal linking

Context events should be queried by:

- overlap with a date
- proximity to a date
- active status
- event type
- affected metric
- severity

Example query:

```text
Find context events occurring zero to two days before an HRV deviation.
```

### Why chat history is insufficient

Chat history alone cannot reliably answer:

- Which injuries are active?
- Which dates were affected by travel?
- What context overlaps this HRV anomaly?
- Which schedule constraints apply this week?
- Which earlier interpretation did the athlete correct?

These require structured records.

---

## 8. Athlete State Layer

The athlete-state layer represents the system's current understanding of the athlete.

It is derived from:

- recent activities
- daily metrics
- active context events
- current goals
- training phase
- recent adherence
- prior interpretations

### Example state

```text
current_goal: improve 10 km performance
training_phase: base
recovery_status: uncertain
active_pain: left Achilles
schedule_constraint: no training Thursday
recent_run_consistency: moderate
current_hrv_signal: below baseline
hrv_interpretation_confidence: low
```

### Purpose

A state layer avoids forcing every rule or AI call to reconstruct the athlete's situation from raw records.

### Important distinction

Athlete state is not:

- raw Garmin data
- a single context event
- an AI-generated paragraph
- an activity record

It is a structured and updateable summary of the current situation.

The first version may calculate state dynamically instead of storing it in a table.

---

## 9. Rule Engine

The rule engine produces transparent interpretations from metrics, context, and state.

### Initial HRV rule

If:

- HRV is below its defined baseline
- and a `social_event`, `alcohol`, `late_night`, or `poor_sleep` event occurred within the previous zero to two days

Then:

- reduce confidence that training fatigue is the sole explanation
- mention the relevant alternative context
- continue monitoring the trend
- do not advise ignoring HRV

### Initial pain rule

If:

- an active pain event concerns Achilles, knee, calf, foot, shin, hip, or hamstring
- and running volume or intensity is planned to increase

Then:

- flag the planned increase
- recommend conservative progression
- request symptom monitoring
- avoid medical diagnosis

### Rule output

Rules should return structured results.

Example:

```python
Interpretation(
    signal="hrv_below_baseline",
    confidence="low",
    contributing_factors=["late_night", "alcohol"],
    message_key="hrv_alternative_explanation",
    monitoring_days=3,
)
```

The explanation layer can then turn this into user-facing text.

---

## 10. Explanation Engine

The first explanation engine should be rule-based and template-driven.

It converts structured metrics and rule results into concise output.

Example:

```text
HRV was below its recent baseline on 19 and 20 July.

A late social event was recorded on 18 July. This provides a plausible
non-training explanation, so confidence that the HRV decline was caused only
by training fatigue is lower.

Continue monitoring the following days rather than ignoring the signal.
```

The engine must:

- distinguish observation from interpretation
- state uncertainty
- avoid causal overclaiming
- avoid medical diagnosis
- identify relevant supporting context

---

## 11. AI Coach Layer — Later

AI should be added only after:

- Garmin synchronization works
- database persistence works
- duplicate prevention works
- metrics are tested
- context events are queryable
- athlete state exists
- basic rules work

### Appropriate AI uses

- parse natural-language notes into structured context
- improve explanation wording
- answer coaching questions
- generate detailed workouts
- produce weekly reviews
- adjust plans with athlete confirmation
- summarize relevant scientific evidence

### Inappropriate AI uses

- calculating metrics
- handling Garmin credentials
- storing raw application state
- replacing database queries
- receiving all raw history by default
- making unsupported medical diagnoses
- silently changing training plans

### Cost levels

#### Level 0: no AI

Use for:

- synchronization
- database writes
- metrics
- anomaly detection
- state updates
- rules
- basic explanations

#### Level 1: inexpensive AI

Use for:

- parsing context notes
- short explanations
- simple coach conversation

#### Level 2: strong AI

Use for:

- weekly review
- plan adjustment
- workout generation

#### Level 3: frontier AI

Use only with explicit confirmation for:

- deep baseline analysis
- monthly or block-level review
- major goal changes

---

## 12. CLI Layer

The CLI is the first user interface.

Initial target commands:

```bash
pace --help
pace db init
pace sync --days 14
pace activities
pace activities --sport run
pace metrics summary --days 30
pace note add --date 2026-07-18 --type social_event "Var ute sent"
pace note list
pace explain hrv --days 14
```

The CLI should:

- call services
- format results
- return useful exit codes
- display clear errors

The CLI should not:

- contain SQL
- parse Garmin payloads
- calculate metrics directly
- contain coaching rules

---

# Proposed Package Structure

```text
src/pace/
├── cli/
│   ├── app.py
│   ├── db_commands.py
│   ├── sync_commands.py
│   ├── activity_commands.py
│   ├── metric_commands.py
│   ├── note_commands.py
│   └── explanation_commands.py
├── config/
│   └── settings.py
├── database/
│   ├── engine.py
│   ├── session.py
│   └── models/
│       ├── activity.py
│       ├── daily_metric.py
│       ├── context_event.py
│       └── sync_run.py
├── integrations/
│   └── garmin/
│       ├── client.py
│       ├── auth.py
│       ├── normalizers.py
│       └── exceptions.py
├── repositories/
│   ├── activity_repository.py
│   ├── daily_metric_repository.py
│   ├── context_event_repository.py
│   └── sync_run_repository.py
├── services/
│   ├── garmin_sync_service.py
│   ├── activity_service.py
│   ├── metric_service.py
│   ├── context_service.py
│   └── explanation_service.py
├── metrics/
│   ├── volume.py
│   ├── hrv.py
│   ├── resting_heart_rate.py
│   └── sleep.py
├── state/
│   ├── models.py
│   └── builder.py
├── rules/
│   ├── models.py
│   ├── hrv_rules.py
│   └── pain_rules.py
└── explanations/
    ├── models.py
    └── templates.py
```

This is a target structure, not a requirement to create every file immediately.

Only add modules when a real milestone requires them.

---

# Failure Handling

## Partial Garmin failures

Daily Garmin endpoints may fail independently.

A failed endpoint should not always cancel the entire synchronization.

The sync service should:

- record which endpoint failed
- continue when safe
- store successful data
- mark the sync as partial
- show a clear summary

## Duplicate protection

Synchronization must be idempotent.

Running:

```bash
pace sync --days 14
pace sync --days 14
```

should not create duplicate activities or daily metrics.

## Missing data

Missing Garmin metrics should be represented as missing values, not converted to zero unless zero is semantically correct.

## Logging

Logs may include:

- endpoint name
- requested date range
- record counts
- retry attempts
- exception type

Logs must not include:

- Garmin password
- session-token contents
- full sensitive context notes by default

---

# Testing Strategy

Tests should be separated by layer.

```text
tests/
├── unit/
│   ├── metrics/
│   ├── rules/
│   ├── normalization/
│   └── state/
├── integration/
│   ├── database/
│   └── repositories/
└── services/
    └── test_garmin_sync_service.py
```

Use temporary or in-memory SQLite databases in tests.

Tests must never operate on the real development database or Garmin token directory.

---

# Architectural Constraints

The following constraints apply until an explicit decision changes them:

- Garmin is the only external training-data provider.
- The system is single-user.
- The system runs locally.
- SQLite is the version 1 database.
- The CLI is the first interface.
- Numerical metrics are calculated in Python.
- Context memory is structured and persistent.
- Athlete state precedes advanced coaching logic.
- Rule-based interpretation precedes AI interpretation.
- AI is optional and introduced later.
- Credentials and tokens are never sent to AI.
- A web framework is not required for version 1.
- Cloud infrastructure is not required for version 1.
