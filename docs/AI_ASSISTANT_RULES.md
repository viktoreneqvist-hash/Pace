# AI Assistant Rules

## Purpose

This file defines how AI assistants should work inside the Pace repository.

The goal is not only to generate code.

The goal is to:

- preserve architectural decisions
- teach engineering concepts
- improve the system incrementally
- avoid unnecessary complexity

---

# Before Making Changes

An AI assistant must understand:

- PROJECT_VISION.md
- ARCHITECTURE.md
- DECISIONS.md
- ROADMAP.md

before suggesting major architectural changes.

If a proposed change conflicts with these files:

1. explain the conflict
2. explain the trade-off
3. ask for an explicit decision

Do not silently override previous decisions.

---

# Core Product Principles

## 1. Garmin First

Garmin Connect is the only external training data source in v1.

Do not introduce:

- Strava
- additional providers
- provider abstraction layers

unless there is a clear requirement.

---

## 2. Single User

The system is built for one athlete.

Do not introduce:

- authentication systems
- user accounts
- permissions
- multi-tenant architecture
- cloud deployment

unless explicitly requested.

---

## 3. Local First

The application should run locally.

Prefer:

- SQLite
- local files
- local configuration
- CLI workflows

Avoid unnecessary infrastructure.

---

# Architecture Rules

## Separation of Responsibilities

Keep clear boundaries.

### Integration layer

Responsible for:

- external APIs
- authentication
- fetching data
- provider errors

Not responsible for:

- metrics
- coaching logic
- AI calls

---

### Database layer

Responsible for:

- persistence
- queries
- transactions

Not responsible for:

- interpretation
- recommendations

---

### Metrics layer

Responsible for:

- calculations
- statistics
- trends

Not responsible for:

- explanations
- coaching advice

---

### Rule layer

Responsible for:

- transparent interpretation

Not responsible for:

- numerical calculations
- language generation

---

### AI layer

Responsible for:

- explanation
- conversation
- reasoning over structured information

Not responsible for:

- calculating metrics
- storing application state
- replacing deterministic code

---

# Coding Principles

Prefer:

- readable code
- explicit logic
- small modules
- type hints
- tests
- clear naming

Avoid:

- premature abstraction
- unnecessary frameworks
- clever shortcuts
- hidden behavior

---

# Before Writing Large Amounts of Code

Explain:

1. What problem is being solved?
2. Why does this component exist?
3. Where does it fit in the architecture?
4. What alternatives exist?
5. What are the trade-offs?

---

# Data Principles

## Raw Data

Preserve raw external data when useful.

Reasons:

- debugging
- future reprocessing
- auditing

---

## Deterministic Before AI

If Python can calculate something exactly:

Python should calculate it.

Examples:

- distance
- training volume
- HRV baseline
- trends
- deviations

Do not ask an LLM to calculate numerical values.

---

# AI Usage Rules

AI should receive:

- relevant metrics
- athlete state
- context events
- rule outputs

AI should not receive:

- passwords
- tokens
- unnecessary raw history
- database dumps

---

# Memory Rules

Chat history is not application memory.

Important athlete information should become structured data.

Examples:

- injuries
- goals
- schedule constraints
- training preferences
- contextual events

Store these in the database.

---

# Testing Rules

Before considering a feature complete:

- add tests
- verify edge cases
- verify duplicate behavior
- verify failure handling

Tests must not:

- use real user data
- modify production data
- require external credentials

---

# Decision Tracking

Important architectural decisions should be added to:

DECISIONS.md

Examples:

- changing database
- changing architecture
- adding external services
- introducing AI components

---

# Review Behavior

The AI assistant should behave as:

- technical mentor
- senior engineer reviewer

It should:

- identify weak assumptions
- question unnecessary complexity
- explain trade-offs
- suggest improvements

It should not automatically agree with proposals.

---

# Learning Priority

When introducing new technology:

Explain:

1. intuition
2. technical definition
3. implementation relevance
4. alternatives
5. trade-offs

The goal is understanding, not only implementation.