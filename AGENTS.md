# Pace contributor instructions

Pace is a private, local-first, single-user Garmin system for running and
cycling. Keep the implementation small, explicit, and understandable.

## Read before changing code

Read these files in order:

1. `docs/PROJECT_VISION.md`
2. `docs/ARCHITECTURE.md`
3. `docs/DECISIONS.md`
4. `docs/ROADMAP.md`
5. `docs/AI_ASSISTANT_RULES.md`
6. relevant Git history

Record a material architecture or product change in `docs/DECISIONS.md`.

## Architecture invariants

Preserve this data flow and implementation order:

```text
Garmin provider
    -> sync service (client -> normalization -> repositories)
    -> local database
    -> deterministic analysis services
    -> context memory
    -> athlete state
    -> rules
    -> AI later
```

- Only the Garmin integration may know Garmin client APIs and payload shapes.
- Normalizers turn provider payloads into Pace's internal contract.
- Repositories own queries and persistence, not analysis or UI text.
- Services coordinate transactions and workflows.
- Analysis returns deterministic facts without coaching thresholds.
- The CLI parses input, invokes services, and formats output.
- AI must never calculate canonical metrics or receive raw Garmin payloads,
  database dumps, passwords, or tokens.

## Resolved v1 decisions

- `Europe/Stockholm` is the athlete timezone. Store activity instants as UTC
  and derive local calendar dates at query and analysis boundaries. Travel may
  be an athlete context event, but it never changes v1's activity timezone.
- Only normalized `run` and `ride` activities count in metrics. Every other
  Garmin activity type normalizes to `other` and is strictly excluded from all
  training totals, activity counts, active days, and comparisons.
- A sync batch is at most seven inclusive calendar days. Historical import uses
  explicit, repeatable batches with `pace sync --days 7 --end-date YYYY-MM-DD`;
  do not add a background job or checkpoint system without evidence it is
  needed.
- Activity identity is `(provider, provider_activity_id)` and daily recovery
  identity is `date`. Re-running a batch must not create duplicates.
- V1 is a local append/update archive. Absence from a later Garmin response
  never implies deletion; do not add destructive reconciliation without a new
  decision and an auditable deletion contract.
- A daily record contains the latest successful raw snapshot for each recovery
  endpoint. If one endpoint fails, preserve its previous normalized values and
  raw snapshot while updating endpoints that succeeded.
- SQLite and Garmin token files use owner-only permissions. The operating
  system's disk protection is the privacy boundary for this single-user local
  application; do not add application-level database encryption or key
  management without a new decision.
- The optional OpenAI key defaults to `.local/pace.env` in each local clone.
  It must be owner-only and Git-ignored; `OPENAI_API_KEY` in the environment
  remains an explicit override. Never restore a developer-specific secrets
  path as the shared default.
- Missing source values remain `None`. Do not convert unknown distance,
  recovery, or sleep values to zero.
- Detailed Garmin performance import is a separate at-most-seven-day command.
  It fetches only locally stored `run` and `ride` activities and persists a
  normalized scalar and split contract. Never store or send detailed Garmin
  routes, coordinates, chart samples, or raw detail payloads.
- Running pace and cycling power targets require Python to report verified
  same-sport evidence from the last 12 weeks and at least two same-sport
  activities in the last 14 days. Cycling power specifically requires the
  explicit `ride_20min_power_test` benchmark. The sole exception is cycling
  riding with confirmed Garmin heart-rate zones: it needs two recent rides and
  a manually confirmed local Garmin zone profile. Zones 1–5 are permitted.
  The coach model, not Python, decides their distribution from selected facts
  and explains its reasoning. Never derive zones from observed heart rate or
  prescribe cycling pace. These are eligibility gates, never target
  calculations or fitness scores.
- Plan generation is an explicit, stateless AI call that can create only a
  local `draft` plan version. It must not change an accepted plan. Acceptance,
  session feedback, and a subsequent revision draft are separate athlete
  actions; feedback text is included in an AI revision only when the athlete
  marked that individual note as shareable.
- Every new plan uses the current structured plan contract. Its coaching
  assessment must cite one or more IDs from the selected, provenance-labelled
  fact catalog and must contain explicit inference, rationale, uncertainty,
  and general-principle fields. Do not send raw payloads, note text, database
  dumps, or an unbounded prior plan to the AI. Legacy drafts remain readable
  but cannot be accepted or revised; generate a fresh draft instead.
- Sport role and availability are athlete preferences. The coach model decides
  session mix, frequency, and progression from selected Pace facts, then makes
  its conclusions and uncertainties reviewable. Python enforces selected
  weekdays and explicit daily time caps. Every planned cycling session requires
  distance, duration, and an allowed Garmin zone target. Its additional
  primary target is a structured RPE, verified run pace, verified cycling
  power, or none — never free text. Cycling pace is forbidden.
- Revisions preserve the accepted parent's block dates and block outline. A
  revision remains a draft until accepted; once one sibling revision is
  accepted, other siblings are stale and cannot be accepted.
- SQLite foreign keys are enabled on every application connection. `pace db
  init` checks existing SQLite foreign-key integrity before an upgrade. Plan
  readiness also blocks drafting when otherwise-contiguous Garmin history is
  more than one day stale.
- The plan terminal review and HTML report are local presentation layers over
  an already persisted plan. They must not call an AI model, sync Garmin, or
  mutate the plan. HTML reports are written only under Git-ignored `reports/`
  with owner-only permissions and omit raw payloads and all private note text.
- K1 coaching knowledge is a checked-in, curated local library, never a
  runtime web search. Python selects at most five topic-relevant briefs for
  an AI request; model references are optional but, when present, must be one
  of those selected IDs. Briefs state supported claims and limitations, and cannot override
  local Pace facts, athlete preferences, eligibility gates, or safety rules.
  Do not add automatic source ingestion, raw-paper storage, embeddings, or a
  vector database without a new product decision.
- K2 coach dialogue reads exactly one accepted, active plan and current selected
  Pace facts. Its in-terminal dialogue history exists only in process memory
  and is discarded on exit; it is not application memory. A same-day
  replacement or skip is only a validated, unsaved draft. It must never alter,
  accept, or overwrite a plan; persistent changes remain a separate revision
  draft and explicit athlete acceptance.
- Coaching ambition is a stored athlete preference: `cautious`, `balanced`, or
  `ambitious`. It is supplied to plan drafting and coach dialogue as intent,
  never a numerical volume/intensity rule or permission to bypass factual,
  availability, evidence, or acceptance boundaries. The coach model must
  explain how it affected a draft or why the facts prevented that effect.
- Race records have an explicit `active`/`cancelled` lifecycle. Correct or
  delete only unused future races. Once a plan or Garmin evidence references a
  race, its facts and identity are historical. A cancelled race is retained for
  audit but cannot define or be accepted by a new plan, or receive new Garmin
  race evidence; cancellation is blocked for accepted-plan and evidence use.
- L1 feedback trends use only explicit structured session feedback: optional
  RPE for completed/limited sessions and optional reason codes for
  limited/skipped sessions. Never infer a missing outcome, send private note
  text through the trend path, create context automatically, claim causality,
  or automatically alter a plan. Six recent feedback records are required for
  trend use; four prior records are required for a comparison.
- L2 dashboard is a local, owner-only, read-only HTML/SVG view. It must not
  call AI, sync Garmin, expose raw payloads/private note text, or mutate data.
- L3 personalisation uses only a current deterministic 56-day explicit-feedback
  summary and athlete-confirmed coach principles. A principle expires to review
  after 84 days, is never inferred as fact, and cannot alter a plan automatically.
- Pace's coach voice is direct, factual, and unsentimental. Do not add praise,
  therapy language, generic wellness language, or routine care-provider
  referrals for ordinary fatigue, poor sleep, or discomfort. This is not a
  license to prescribe through pain or give medical advice: say plainly when
  the factual situation supports reducing or skipping a session.
- New plan contract v3 sessions persist a structured workout: warmup, steady,
  interval (with repetition and recovery), and cooldown blocks. Python applies
  the same factual target-evidence gates to every block. v2 plans stay readable
  as historical records but cannot be revised; regenerate before changing them.
  A same-day Garmin activity is only a candidate when evaluating a planned
  workout, never proof that its structure was completed. Explicit feedback
  remains the only completion outcome and plans are never altered automatically.
- A plan checkpoint may recommend a new draft or bounded revision when the
  detailed window ends or a race approaches. It must never generate, accept, or
  overwrite a plan. Every active race inside a generated detailed window must
  remain visible as a same-date, same-sport session with its stored A/B/C role.
- Workout form is model-owned coaching judgment over selected Pace facts and
  block purpose. Do not add a fixed workout-template rotation for cosmetic
  variety. Python continues to own all availability, sport, target, evidence,
  and persistence gates.
- Split-aware workout evaluation may expose normalized Garmin split facts and
  planned-versus-actual summary differences. It must not infer interval
  compliance or completion; explicit athlete feedback remains authoritative.
- Personalisation patterns are non-persistent observations over explicit
  feedback and appear only after the existing 56-day thresholds. They must
  state their data counts, remain non-causal, and never alter a plan.
- Pace Home and transparent analysis are local read-only presentation and
  fact layers. They may compose existing services and write owner-only reports,
  but must not sync Garmin, call AI, mutate plans, invent a proprietary load
  score, or treat missing data as zero.
- Synthetic coach evaluation uses reviewed fake facts only. The deterministic
  contract runs in the normal test suite; a real-model evaluation requires an
  explicit live command and must never use real athlete data or run in CI.
- Garmin workout export is deferred. Do not add calendar/device writes or other
  externally mutating plan delivery without a new product and safety decision.
- `pace serve` is a loopback-only local presentation layer. Bind it only to
  `127.0.0.1`; do not add hosted access, accounts, remote listeners, or API
  keys/tokens in browser-delivered HTML or JavaScript without a new decision.
  Browser coach dialogue is bounded in process memory only. Every durable UI
  write requires same-origin CSRF confirmation and must call the existing
  validated service; an LLM may prepare a card but must never write context,
  feedback, preferences, races, or plans directly. Plan adjustments remain
  review-only until an explicit revision workflow is designed.

## Safety and privacy

- Never commit `.env`, `data/`, `.local/`, SQLite sidecars, credentials, tokens,
  or real Garmin payloads.
- Never read or print token contents.
- Never log passwords, MFA codes, token values, full raw payloads, or sensitive
  context notes.
- Tests must use synthetic fixtures, an isolated database, and fake Garmin
  clients. They must not log in, call Garmin, or touch the real database or
  token directory.
- Raw Garmin payloads exist for local debugging and re-normalization only.
  Future AI context must be built from normalized facts and explicitly selected
  context events.
- Pace does not diagnose health conditions. Coaching policy requires an
  explicit product decision and belongs after athlete state and transparent
  rules.

## Local workflow

```bash
uv run pace db init
uv run ruff check .
uv run pytest -q
```

Use Alembic for every schema change. Validate migrations against an isolated
temporary database. Keep external calls bounded, preserve successful data
across partial recovery failures, and add tests only where they reduce a
specific data-loss, privacy, calculation, or migration risk.
