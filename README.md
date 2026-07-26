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

See `AGENTS.md` for implementation invariants, privacy rules, and the local validation
workflow.
