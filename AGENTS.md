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
- Missing source values remain `None`. Do not convert unknown distance,
  recovery, or sleep values to zero.
- Detailed Garmin performance import is a separate at-most-seven-day command.
  It fetches only locally stored `run` and `ride` activities and persists a
  normalized scalar and split contract. Never store or send detailed Garmin
  routes, coordinates, chart samples, or raw detail payloads.

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
