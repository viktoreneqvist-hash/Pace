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
stores the Garmin password in the database or repository. The first activity sync is intentionally
limited to seven calendar days. It imports activities plus available daily recovery
signals: HRV, sleep, stress, Body Battery, resting heart rate, and training readiness.

```bash
uv run pace --help
uv run pace garmin login
uv run pace sync --days 7
uv run pace metrics summary
```
