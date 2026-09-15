# Contributing to Pace

Pace is an early local-first project. Small, reviewable changes with tests are
the best way to contribute.

## Before you start

1. Read [AGENTS.md](AGENTS.md) for the architecture and privacy boundaries.
2. Search existing issues before opening a new one.
3. Discuss large product, schema, privacy, or coaching-policy changes in an
   issue before implementing them.

## Local setup

```bash
git clone https://github.com/viktoreneqvist-hash/Pace.git
cd Pace
uv sync
uv run pace db init
```

Run the quality checks before submitting a pull request:

```bash
uv run ruff check .
uv run pytest -q
git diff --check
```

## Pull requests

- Keep one pull request focused on one problem.
- Explain the user-visible behavior and the architectural reason for the change.
- Add or update tests for behavior changes.
- Update the relevant design document when a decision or boundary changes.
- Never include real Garmin data, API keys, tokens, databases, generated
  reports, or private athlete context.
- Do not make network calls from the default test suite.

## Database changes

Schema changes require an Alembic migration. Verify both a blank upgrade and
the full test suite. Do not edit an existing released migration to change
history.

## Coaching and AI changes

Pace keeps facts, inference, and athlete preference separate. The model may
make coaching judgments, but Python must validate saved plans and must not
invent missing facts. New medical, nutrition, or injury-diagnosis behavior is
out of scope unless it has first been explicitly designed and approved.

## Reporting bugs

Use the bug-report template. Remove names, email addresses, notes, tokens,
database contents, and raw Garmin payloads from logs and screenshots.
