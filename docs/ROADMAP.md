# Pace — Development Roadmap

## Goal

Build a private, local-first endurance coaching system.

The development order is intentionally:

1. Reliable data
2. Deterministic analysis
3. Athlete context
4. Interpretation
5. AI assistance

AI is added only after the underlying system can produce trustworthy information.

---

# Phase 0 — Project Reset

## Goal

Align the existing project with the new architecture.

Tasks:

- [ ] Remove Strava integration
- [ ] Rename project concepts if needed
- [ ] Update documentation
- [ ] Clean unused dependencies
- [ ] Confirm local-first structure

Success criteria:

- Documentation matches implementation
- No outdated architectural assumptions remain

---

# Phase 1 — Python Application Foundation

## Goal

Create a clean and maintainable Python application.

Tasks:

- [x] Python environment
- [x] uv dependency management
- [x] src layout
- [ ] CLI framework
- [ ] Configuration system
- [ ] Logging system
- [ ] Error handling conventions

Learn:

- Python packaging
- application structure
- dependency management
- configuration management

Success criteria:

The application can run through clear CLI commands.

Example:

```bash
pace --help

Phase 2 — Database Foundation
Goal
Create reliable local data storage.
Database:
SQLite
Tasks:

Database initialization command

SQLAlchemy setup

Migration strategy

Activity model

Daily metric model

Context event model

Sync history model
Important requirements:

Unique constraints

Duplicate prevention

Test database separation
Success criteria:
Running synchronization multiple times does not create duplicates.


Phase 3 — Garmin Integration
Goal
Automatically collect athlete data.
Primary source:
Garmin Connect
Tasks:

Garmin authentication

Token/session persistence

Activity synchronization

Daily health synchronization

Recovery metric synchronization

Raw payload storage

Data normalization
Data collected:
Activities:
distance
duration
heart rate
power
cadence
elevation
training effect
Daily metrics:
HRV
resting heart rate
sleep
stress
Body Battery
training readiness
Success criteria:
A complete Garmin history can be imported into the local database.


Phase 4 — Deterministic Metrics
Goal
Generate useful insights without AI.
All calculations happen in Python.
Tasks:
Training volume

Weekly running distance

Weekly cycling duration

Training frequency

Longest sessions

Training progression
Recovery metrics

HRV baseline

HRV deviation

Resting heart-rate baseline

Sleep trends

Recovery trends
Training analysis

Intensity distribution

Consistency metrics

Training load estimation
Requirements:
Metrics must be:
deterministic
tested
explainable
Success criteria:
The system can answer factual questions about training history without AI.


Phase 5 — Context Memory
Goal
Store information Garmin cannot know.
Tasks:

Context event model

Add context through CLI

Query context by date

Link context to metrics
Initial context types:
illness
injury
pain
alcohol
poor sleep
travel
work stress
social events
schedule constraints
athlete feedback
Example:
pace note add \
--type social_event \
--date 2026-07-20 \
"Late evening and poor sleep"
Success criteria:
The system can combine physiological data with athlete-provided context.


Phase 6 — Athlete State
Goal
Create a structured representation of the athlete's current situation.
The system should understand:
current goal
training phase
recent training
recovery status
active injuries
schedule constraints
confidence in signals
Tasks:

Define athlete state model

Build state calculation

Update state after synchronization

Test state transitions
Success criteria:
The system can summarize the athlete's current condition without reading raw history.


Phase 7 — Rule Engine
Goal
Create transparent coaching logic.
Rules should interpret metrics and context.
Initial rules:
Recovery
Example:
If:
HRV below baseline
poor sleep
recent alcohol/social event
Then:
reduce confidence that training fatigue is the only explanation
recommend monitoring
Injury
Example:
If:
active Achilles pain
increasing running load
Then:
flag progression risk
suggest conservative approach
Requirements:
Rules must be:
explicit
testable
explainable
Success criteria:
The system can produce structured interpretations without AI.


Phase 8 — Explanation Engine
Goal
Convert structured insights into understandable coaching feedback.
Before AI:
Use templates.
Example:
Input:
HRV below baseline
Late social event recorded
Confidence low
Output:
HRV has been below your normal range for two days.
A recent late evening may explain part of this change.
Continue monitoring before changing training.
Success criteria:
The system can communicate reasoning clearly.


Phase 9 — AI Integration
Goal
Add AI as a reasoning and communication layer.
AI should receive:
metrics
athlete state
relevant context
rule outputs
AI should not receive:
raw database dumps
credentials
unnecessary history
Tasks:

Structured outputs

Tool calling

Context retrieval

Coaching conversation
Use cases:
explain trends
answer questions
summarize weeks
discuss training decisions
Phase 10 — Advanced Coaching Agent
Goal
Build a true coaching assistant.
Capabilities:
training planning
workout generation
race preparation
scientific literature retrieval
adaptive recommendations
long-term memory
Prerequisites:
All previous phases must be reliable.
Current Priority
The immediate development order is:
Garmin integration
Database reliability
Deterministic metrics
Context memory
Athlete state
Rule engine
AI coach
The project should resist adding complexity before these foundations work.