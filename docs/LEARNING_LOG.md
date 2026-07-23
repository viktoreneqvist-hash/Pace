# Learning Log

This document records important lessons learned during development of Pace.

The purpose is to track engineering understanding, not only completed tasks.

---

# 2026-07 — Architecture Reset

## Background

After experimenting with external Garmin AI tools and rapid application builders, the project direction was reconsidered.

The main lesson:

A useful AI coach is not primarily an AI problem.

It is a data, architecture, and memory problem.

---

# Lessons Learned

## 1. AI is only as good as the system around it

An LLM can generate convincing text without actually understanding the athlete.

A coaching system needs:

- reliable data
- historical context
- explicit state
- transparent reasoning

AI should operate on structured understanding.

---

## 2. Data quality matters more than AI capability

A simple model with excellent athlete data can outperform a powerful model with poor context.

Important data:

- training history
- recovery
- injuries
- goals
- life events
- athlete feedback

---

## 3. Garmin is more valuable than expected

Garmin provides information closer to coaching decisions:

- HRV
- sleep
- recovery
- readiness
- stress
- training metrics

Activity platforms mainly describe what happened.

A coach needs to understand why performance changes.

---

## 4. Context memory is essential

Physiological data does not explain itself.

Example:

Signal:
HRV Decreased


Possible explanations:

- accumulated fatigue
- alcohol
- illness
- stress
- poor sleep
- travel

Without context, interpretation is uncertain.

---

## 5. Deterministic systems should come before AI

Anything that can be calculated reliably should be calculated in code.

Examples:

- training volume
- trends
- baselines
- deviations

Benefits:

- reproducibility
- testing
- lower cost
- transparency

---

# Engineering Lessons

## Databases

A database is not just storage.

It provides:

- persistence
- relationships
- querying
- historical memory

The design of stored data shapes what the system can understand.

---

## APIs

External integrations require:

- authentication
- token management
- error handling
- synchronization strategy

Successful API integration is more than making one request work.

---

## Synchronization

Data import must be idempotent.

Running:
sync
sync
sync


should not create duplicates.

---

## Architecture

Good architecture is about controlling complexity.

A smaller system with clear boundaries is often better than a larger system with more technologies.

---

# Concepts To Learn Further

## High priority

- Database modeling
- SQLite internals
- SQLAlchemy patterns
- API authentication
- OAuth
- Idempotent synchronization
- Testing strategies
- Data normalization

---

## AI Engineering

- Structured outputs
- Function calling
- Retrieval systems
- Embeddings
- RAG
- Agent architecture
- Tool use
- Memory systems

---

## Coaching Science

- Training load models
- Fatigue modeling
- HRV interpretation
- Endurance periodization
- Injury risk factors
- Exercise physiology

---

# Future Lessons

Continue updating this document when:

- a major architecture decision is made
- a technical concept becomes understood
- an experiment changes project direction
- a mistake produces a useful lesson