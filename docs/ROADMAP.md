# Pace — Development Roadmap

## Current position

Pace has completed the original local coaching loop:

```text
Garmin data
    -> local database
    -> deterministic facts and multi-horizon history
    -> structured context and explicit feedback
    -> bounded AI coaching
    -> validated, versioned plans
    -> local Coach, Dashboard, Plan, and Weekly review UI
```

The product is now moving from a private prototype to a documented public
alpha. The detailed history of product decisions remains in
[DECISIONS.md](DECISIONS.md); this file describes the forward plan.

## Completed foundation

### Data and integrity

- [x] Preserve the former Strava version in Git history and make Garmin the
  only active provider
- [x] SQLite, SQLAlchemy repositories, and a forward Alembic migration chain
- [x] Idempotent activity and recovery sync with seven-day provider batches
- [x] Endpoint-aware partial failure, authentication, and rate-limit handling
- [x] UTC activity storage with Stockholm-local coaching dates
- [x] Owner-only local database, tokens, and secrets

### Facts, context, and interpretation

- [x] Deterministic training and recovery summaries
- [x] HRV, resting-heart-rate, and sleep baselines with explicit data quality
- [x] Structured illness, pain, travel, alcohol, poor-sleep, work-stress, and
  schedule context
- [x] Athlete state and transparent recovery rules
- [x] Multi-horizon training evidence that cannot be manipulated by one high
  or low week
- [x] Explicit separation of athlete facts, model inference, and uncertainty

### Planning and personalization

- [x] Stored A/B/C races and explicit general-plan mode
- [x] Five sport roles, weekly availability, coaching ambition, and cycling
  heart-rate zones
- [x] Historical capacity and privacy-minimized verified performance evidence
- [x] Race-specific or general plan generation
- [x] Structured workouts with continuous, warm-up, interval, recovery, and
  cool-down steps when useful
- [x] Atomic Python validation and immutable accepted plan versions
- [x] Session feedback, workout comparison, plan revision, and checkpoints
- [x] Personalization evidence derived only from explicit feedback
- [x] Reviewed local coaching knowledge and source-linked principles

### Product interface

- [x] Loopback-only local web application and macOS Finder launcher
- [x] Guided first-run setup for key, Garmin, preferences, zones, history,
  races, and first plan
- [x] Coach chat with bounded history and confirmable action cards
- [x] Safe slash commands for local status, sync, and weekly review
- [x] Persistent navigation across Coach, Dashboard, Plan, and Weekly review
- [x] Information-rich charts and structured plan presentation
- [x] Browser settings for normal operations so the terminal is optional

## Release L0 — public alpha hardening

Goal: make the repository safe and understandable for unknown users without
pretending that the product is finished.

- [x] English public README with setup, architecture, privacy, and limitations
- [x] Contribution and vulnerability-reporting guides
- [x] Issue and pull-request templates
- [x] Ignore local editor, build, coverage, database, token, secret, and report
  artifacts
- [x] Single installed source for the displayed application version
- [x] Local Host-header allowlist and restrictive browser security headers
- [x] S1 threat model, source review, localhost attack checks, dependency audit,
  and full-history secret scan
- [x] Verify a clean installation in an isolated temporary environment
- [x] Scan all Git history with Gitleaks before publication
- [ ] Review the newest compatible `garminconnect` release with a real login and
  read-only sync
- [ ] Add a synthetic-data product screenshot or short demo
- [x] Enable GitHub Dependabot vulnerability alerts and repository topics
- [ ] Enable GitHub secret scanning and private vulnerability reporting when
  the repository visibility and account features allow them
- [ ] Choose public repository visibility and the first release tag only after
  the release gate passes

## L1 — first external-user feedback

Goal: learn where installation and normal use fail for people other than the
author.

- [ ] Test clean installation on at least two separate macOS machines
- [ ] Record setup completion, Garmin failure mode, and first-plan success
  without collecting private athlete data
- [ ] Improve errors for missing tools, unsupported Python, Garmin rate limits,
  MFA, missing API credit, and failed plan validation
- [ ] Add an in-app version and diagnostics page with copy-safe, sanitized output
- [x] Use English for the v0.1 product interface and coach output; consider
  localization after the public release
- [ ] Decide whether Python 3.13 support is valuable enough to test and maintain
- [ ] Publish a known-issues list from real tester reports

## L2 — coaching quality and trust

Goal: evaluate whether Pace produces better, more stable decisions over time,
not merely more text.

- [ ] Expand synthetic evaluation scenarios for interrupted training, multiple
  races, cycling-heavy athletes, missed feedback, and conflicting recovery data
- [ ] Add regression snapshots for plan structure and evidence references while
  allowing legitimate wording variation
- [ ] Measure plan stability: the same facts should not cause materially
  contradictory retrospective analysis
- [ ] Improve plan-versus-observed workout matching without treating Garmin
  splits as unquestionable session intent
- [ ] Expand the knowledge library only through reviewed, versioned evidence and
  explicit applicability limits
- [ ] Add athlete-visible provenance for important coaching claims

## L3 — maintainability and packaging

Goal: reduce contributor friction after behavior has stabilized.

- [ ] Split the CLI parser, web router, and training-plan service into focused
  modules without changing behavior
- [ ] Add typed service protocols at external and model boundaries
- [ ] Decide distribution method: source clone, standalone macOS package, or a
  uniquely named Python package (the PyPI name `pace` is already occupied)
- [ ] Test an automated upgrade and local-data backup path
- [ ] Add release notes and a documented deprecation policy
- [ ] Add Linux or Windows support only with real maintainers and CI coverage

## Deferred product areas

These require separate design decisions and are not implied by the public-alpha
release:

- mobile application or hosted service;
- multi-user accounts and cloud synchronization;
- direct Garmin workout export;
- calendar integrations and notifications;
- embeddings or a vector database;
- additional providers such as COROS or Strava;
- medication, injury diagnosis, nutrition, and supplements;
- payment, subscriptions, or commercial data processing.

## Release gate

Before every tagged alpha release:

1. Ruff passes.
2. The complete synthetic test suite passes without network access.
3. A blank database reaches the single Alembic head.
4. CLI and local-web smoke tests pass.
5. No secret, real athlete fixture, database, token, or report is tracked.
6. Dependency and vulnerability scans have no unexplained high-risk result.
7. README behavior matches the shipped application.
8. Known limitations are stated instead of hidden.
