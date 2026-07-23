# Pace — Project Vision

## Purpose

Pace is a private, local-first endurance coaching system for running and cycling.

The system should combine:

- Garmin training and recovery data
- deterministic training metrics
- persistent athlete context
- rule-based interpretation
- AI-assisted coaching later

The goal is not to build another report generator.

The goal is to build a persistent coach that understands both:

1. what happened in the athlete's data
2. why it may have happened

Garmin can show that HRV, sleep, resting heart rate, or training load changed.

The athlete can provide context such as:

- illness
- alcohol
- late nights
- travel
- work stress
- pain
- injury
- schedule constraints
- perceived effort
- missed sessions
- equipment changes

Pace should combine both sources before making interpretations.

---

## Primary User

Pace is initially built only for Viktor.

The project does not need:

- multiple users
- user registration
- cloud authentication
- public deployment
- subscription infrastructure
- organization or team support

Single-user operation is an intentional product and architecture decision.

---

## Primary Data Source

Garmin Connect is the only external training-data source in the first version.

Garmin was chosen because it provides both activity data and recovery-related data, including:

- running and cycling activities
- heart rate
- HRV
- resting heart rate
- sleep
- stress
- Body Battery
- training readiness
- recovery time
- device-derived training metrics

Strava is not part of the planned system.

Existing Strava integration code should be removed rather than maintained as a second provider.

---

## Product Principles

### 1. Code calculates facts

Python should calculate all numerical values.

Examples:

- weekly running distance
- cycling duration
- training frequency
- HRV baseline
- HRV deviation
- resting heart-rate baseline
- recent training volume
- activity trends
- anomaly flags

These calculations must be:

- deterministic
- reproducible
- testable
- inexpensive
- explainable

A language model must not be responsible for calculating values that Python can calculate exactly.

### 2. Context changes interpretation

A physiological signal should not be interpreted without relevant athlete context.

Example:

```text
Garmin signal:
HRV below baseline for two days

Athlete context:
Late social event and alcohol the previous evening

Interpretation:
The HRV change has a plausible non-training explanation.
Confidence in a training-fatigue interpretation is therefore lower.
```

Context should not cause signals to be ignored. It should change confidence and interpretation.

### 3. AI is not the foundation

The first working system should function without AI.

The foundation consists of:

- Garmin synchronization
- local database
- deterministic metrics
- structured context memory
- athlete-state representation
- rule-based interpretation

AI should later improve:

- natural-language interaction
- explanations
- weekly reviews
- plan adjustments
- workout generation
- discussion with the athlete

AI should reason over compact structured data, not raw Garmin history.

### 4. Incremental updates before full regeneration

New Garmin data should update the system incrementally.

The normal flow should be:

```text
new Garmin data
    ->
database update
    ->
metric update
    ->
state and rule evaluation
    ->
short explanation when relevant
```

The system should not regenerate an expensive full coaching report after every synchronization.

### 5. Local-first and private

The first version should run locally on the user's computer.

Sensitive information must remain local by default, including:

- Garmin credentials
- Garmin session tokens
- raw health and activity data
- injury notes
- contextual life events

Garmin passwords and tokens must never be sent to an AI model.

---

## Initial Product Experience

The first interface should be a command-line application.

Target commands include:

```bash
pace db init
pace sync --days 30
pace activities
pace activities --sport run
pace metrics summary --days 30
pace note add --date 2026-07-18 --type social_event "Var ute sent och sov dåligt"
pace note list
pace explain hrv --days 14
```

The CLI is the first interface, not necessarily the final interface.

A web or mobile interface may be added later if the underlying system proves useful.

---

## V1 Goal

The goal of version 1 is not to build a complete autonomous coach.

The goal is to prove the following core hypothesis:

```text
Garmin data + persistent structured context
    ->
more accurate and useful coaching explanations
```

Version 1 is successful when the system can:

1. synchronize Garmin data reliably
2. store activities and daily recovery metrics
3. avoid duplicate records
4. calculate basic metrics deterministically
5. store athlete context events
6. connect context events to physiological signals
7. explain an HRV deviation without overclaiming
8. run locally through a comprehensible CLI
9. pass automated tests

---

## Long-Term Direction

After the data foundation is reliable, Pace should gradually support:

### Training analysis

- volume progression
- consistency
- intensity distribution
- long-run development
- cycling load
- recovery trends
- fatigue indicators

### Athlete state

- current goal
- current training phase
- active injuries or pain
- current recovery status
- schedule constraints
- recent adherence
- current confidence in available signals

### Coaching

- weekly reviews
- specific workout recommendations
- training-plan adjustments
- race preparation
- recovery guidance
- explanation of why a recommendation was made

### AI capabilities

- parse free-text context into structured events
- answer questions using relevant stored context
- produce concise coaching explanations
- generate detailed workouts
- conduct deeper periodic reviews
- remember athlete corrections and feedback

---

## Secondary Goal: Engineering Education

The project is also a structured way to learn:

- Python application architecture
- Git and version control
- package management with `uv`
- SQLite and SQL
- SQLAlchemy
- database migrations
- external API integration
- authentication and token persistence
- data normalization
- idempotent synchronization
- testing
- observability and error handling
- structured outputs
- tool calling
- memory systems
- retrieval systems
- agent architecture
- AI cost control

Understanding the system is more important than implementing features quickly.

Important components should not be treated as black boxes.

---

## Non-Goals for V1

Version 1 will not include:

- Strava
- multiple users
- cloud deployment
- user accounts
- Supabase
- a TypeScript frontend
- FastAPI unless a real interface requires it later
- autonomous plan changes
- medical diagnosis
- an LLM performing metric calculations
- large raw-history prompts
- automatic expensive AI analysis after every sync

---

## Core Principle

> Use code for facts and calculations.  
> Use structured memory for athlete context.  
> Use rules for transparent interpretation.  
> Use AI later for reasoning, explanation, and discussion.
