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

Garmin authentication and synchronization are deliberately not implemented yet. This reset
creates the structure for them without introducing credentials or network calls.

```bash
uv run pace --help
```
