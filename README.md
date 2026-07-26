## Pace

Pace is a private, local-first endurance coaching system for running and cycling.

Version 1 is Garmin-first: it will store Garmin activity and recovery data locally,
calculate deterministic training metrics, and later combine those facts with structured
athlete context. See `docs/PROJECT_VISION.md` and `docs/ARCHITECTURE.md` for the full design.

### Current foundation

- Python package: `pace`
- Database: local SQLite at `data/pace.db` by default
- External provider: Garmin Connect only
- Interface direction: `pace` CLI

Garmin login stores a reusable session token locally in `.local/garmin_tokens/`. Pace never
stores the Garmin password in the database or repository. Database and token files use
owner-only permissions.

Each sync is intentionally limited to seven calendar days. It imports activities plus
available daily recovery signals: HRV, sleep, stress, Body Battery, resting heart rate,
and training readiness. Re-running the same batch is safe. Use `--end-date` to import
older history in bounded batches.

Activity instants are stored as UTC and evaluated in the fixed athlete timezone
`Europe/Stockholm`. Only Garmin profiles explicitly normalized as running or cycling
count in metrics; every other activity is excluded.

```bash
uv run pace --help
uv run pace db init
uv run pace garmin login
uv run pace sync --days 7
uv run pace sync --days 7 --end-date 2026-07-18
uv run pace metrics summary
uv run pace note add --type poor_sleep --date 2026-07-25 "Somnade sent."
uv run pace note list --from 2026-07-19 --to 2026-07-25
uv run pace state show
uv run pace rules evaluate
uv run pace explain
```

### Reviewable plan drafts

After at least 28 contiguous, current Garmin days and a saved preference, Pace
can ask the coach model for a local plan *draft*. It never accepts or alters a
plan automatically. The model receives a small, provenance-labelled fact
catalog rather than raw Garmin payloads or private note text; Python checks
availability, history freshness, structured targets, and plan versioning.

```bash
uv run pace preferences set --sport-role ride_primary --day mon:any --day tue:any
uv run pace zones show --sport ride
uv run pace plan readiness
uv run pace plan draft --days 14
uv run pace plan review --id 3
uv run pace plan report --id 3
uv run pace plan accept --id 2
uv run pace plan today
uv run pace plan feedback --session-id 5 --outcome completed
uv run pace plan revise --id 2 --days 7
uv run pace coach ask --plan-id 2 "Kan jag cykla i stället för dagens löppass?"
uv run pace coach chat --plan-id 2
```

Every cycling session has distance, duration, and a saved Garmin heart-rate
zone. The model can additionally use RPE, verified cycling power, or no
primary target; cycling pace is never generated. Running pace and cycling
power require an eligible, verified same-sport fact. Existing draft plans from
before the current contract remain readable but must be regenerated before
they can be accepted or revised.

`pace plan review` is a readable terminal view. `pace plan report` writes a
self-contained private report to `reports/plan-<id>.html`; open that file in a
browser when you want to read the plan away from the terminal. The directory
and report use owner-only permissions, are ignored by Git, contain no raw
Garmin payloads or private feedback/context-note text, and never change a
plan.

`pace coach ask` is a quick question over one accepted, active plan. `pace
coach chat` keeps a short dialogue only in the running terminal process; it is
discarded when the command exits. Both commands rebuild current local facts for
each turn and may show a same-day plan-adjustment *draft*. A draft is Python
validated but never saved or applied. Use the existing separate `pace plan
revise` flow when you want a persistent plan version.

### Curated coaching knowledge

Pace has a small local library of reviewed coaching briefs. It is not a live
web search and it is not a database of raw papers. Python selects at most
three relevant briefs for an AI question or plan draft, and the model may cite
only those brief IDs. The CLI can show exactly what a brief supports and what
it does not support:

```bash
uv run pace knowledge list
uv run pace knowledge show --id hrv_training_context
```

The library is versioned in `knowledge/`. Updating it is a deliberate reviewed
code change; Pace does not download research or learn from external sources at
runtime.

See `AGENTS.md` for implementation invariants, privacy rules, and the local validation
workflow.
