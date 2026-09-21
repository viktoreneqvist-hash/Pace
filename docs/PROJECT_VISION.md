# Pace — Project Vision

## Purpose

Pace is a private, local-first endurance coach for running and cycling. It
combines observed Garmin history, deterministic software, explicit athlete
context, and bounded AI coaching.

The product is built around one idea:

> A coach should start from what the athlete actually did, not only from what
> the athlete says they can do or wants to achieve.

Pace is therefore more than a Garmin report and less than an autonomous agent.
It maintains a traceable coaching loop in which facts, judgment, and athlete
intent remain separate.

## Intended user and distribution

Pace supports one athlete per local installation. The source can be shared
publicly, but each installation owns its own Garmin session, database, OpenAI
key, settings, plans, and reports.

Version 0.1 does not need:

- multi-user accounts;
- cloud storage or hosted authentication;
- subscription infrastructure;
- organization or team features;
- synchronization between devices.

Single-athlete operation is an intentional architecture boundary, not a claim
that only the original author can use the software.

## Data sources

Garmin Connect is the only training-data provider in v0.1. It supplies activity
and recovery observations, including running and cycling, heart rate, HRV,
resting heart rate, sleep, stress, Body Battery, training readiness, and
recovery time when available.

Only activities normalized as `run` or `ride` affect Pace training facts.
Unknown and unsupported activities remain traceable as `other` but do not
silently change coaching totals.

The athlete supplies facts Garmin cannot observe, such as:

- illness, pain, travel, alcohol, poor sleep, work stress, and schedule limits;
- intended races and their priority;
- sport preference, availability, and coaching ambition;
- whether a planned session was completed and how it felt.

## Responsibility model

### Code calculates and validates facts

Python owns exact, reproducible work:

- normalization and units;
- calendar windows and time zones;
- training duration, distance, frequency, and continuity;
- recovery baselines and data quality;
- race, availability, and sport constraints;
- database integrity and complete plan validation.

Missing data remains missing. An LLM must not calculate values that the
application can calculate exactly or invent evidence that is not present.

### The athlete provides intent and confirmation

The athlete chooses the goal scope: a specific A, B, or C race, or no race.
They also choose practical constraints and report session outcomes. Preference
does not become physiology: an offensive ambition may permit a stronger
proposal, but it cannot create capacity evidence.

An explicit **create plan**, **create revision**, or **save feedback** action is
authorization for that operation. Synchronization, recovery changes, and model
conversation never mutate a plan by themselves.

### AI provides coaching judgment

The model may:

- interpret selected facts and uncertainty;
- answer training questions;
- choose session purpose and workout structure;
- create a detailed one- or two-week plan window inside a longer block;
- write a stable weekly review;
- propose context, feedback, or a plan adjustment for confirmation.

The model receives normalized, bounded facts rather than raw Garmin payloads.
It may use general endurance knowledge, while Pace labels that reasoning as
coaching judgment rather than observed athlete fact. Python validates every
plan before it becomes active.

The athlete may set separate weekly base-training ceilings for running
distance, cycling time, and combined training time. These are hard boundaries,
not targets or capacity evidence. A race-directed plan may propose a temporary
exception, but it remains inactive until the athlete reviews the affected
weeks and explicitly approves that plan version.

## Coaching principles

### History, not one flattering week

Plans use multiple time scales. Recent days matter for entry into the next
week, but repeated historical continuity matters for sustainable capacity. A
single high-volume week cannot independently justify a large progression, and
a short unreported interruption does not erase months of training capacity.

Pace should describe an observed interruption without guessing whether it was
caused by illness, travel, motivation, or something else.

### Context changes interpretation

Context never deletes a physiological signal. It may change the plausible
explanation, confidence, or response. Pace must distinguish observations,
inferences, and uncertainties and avoid causal or medical overclaiming.

### Specificity follows the selected goal

A selected race guides the block. An A race receives full taper priority, a B
race a partial taper and secondary-goal treatment, and a C race is treated as
a hard training event. A race is never an implicit command: the athlete can
explicitly create a general plan even when races are stored.

Workout variety is useful only when it serves capacity, recovery, race demand,
and block purpose. Pace may prescribe continuous endurance, progression,
hills, tempo, threshold work, or structured repetitions. It must not rotate
templates merely to look intelligent.

### Incremental use beats constant regeneration

Garmin sync updates facts. It does not trigger a new plan or an AI call. Pace
keeps a longer block direction but details only the next 7–14 days, then uses
new data and feedback for the next explicitly requested version.

## Product experience

The primary interface is a loopback-only local web application started with
`pace serve` or the macOS launcher. It provides onboarding, settings, sync,
Coach, Dashboard, Plan, and Weekly review views. The CLI remains a supported
fallback for diagnostics, automation, and reproducible development workflows.

The interface should be information-dense and direct rather than a generic AI
chat shell. Users should be able to inspect the evidence behind a recommendation
and should not need to read raw JSON during normal use.

## Privacy and safety

The database, Garmin session, API key, reports, and private context remain local
by default. External connections occur only for explicit Garmin and OpenAI
operations. Garmin credentials, tokens, raw payloads, and database dumps must
never be sent to the model.

Pace is not medical care. Injury diagnosis, medication, nutrition, and
supplement advice remain outside v0.1. The application must not be exposed as
an internet-facing server without a new security architecture.

## Version 0.1 success criteria

Version 0.1 is successful when a new user can:

1. install and start Pace from a clean clone;
2. connect Garmin without leaking credentials or tokens;
3. import bounded history idempotently;
4. understand the local data and AI privacy boundary;
5. configure sport intent, ambition, availability, zones, and races;
6. create a valid general or race-directed plan from observed history;
7. inspect structured sessions and the coach's reasoning;
8. record feedback and use it in a later explicit plan version;
9. read current facts and a stable weekly review in the local interface;
10. run a fully synthetic, network-free test suite.

## Long-term direction

After the local alpha is reliable, Pace may add:

- stronger training-load, intensity-distribution, and durability analysis;
- better plan-versus-observed workout matching;
- richer athlete memory with expiry and provenance;
- broader, versioned scientific coaching knowledge;
- additional tested platforms and packaging;
- export to devices or calendars;
- an optional hosted product only after separate privacy, identity, security,
  and licensing decisions.

## Engineering-education goal

Pace is also a practical way to learn Python architecture, Git, package
management, SQLite, migrations, APIs, authentication, normalization, testing,
structured LLM output, retrieval, memory, and agent boundaries. Important
components should remain understandable rather than becoming black boxes.

## Core principle

> Use code for facts and validation.
>
> Use structured memory for athlete context.
>
> Use AI for bounded coaching judgment.
>
> Keep material changes explicit, local, and reviewable.
