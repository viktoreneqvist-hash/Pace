# Architecture Decisions

## Decision Template

### Decision #

Problem:

Options:

Chosen:

Reason:

Consequences:

---

## Decision #1

Problem:

Package management.

Options:

- pip + venv

- uv

Chosen:

uv

Reason:

Modern Python workflow.

Consequences:

Need to learn uv internals.

---

## Decision #2

Problem:

Database selection.

Options:

- SQLite

- PostgreSQL

- MongoDB

Status:

Chosen

Result:

PostgreSQL

Reason: Vi vill lära oss riktig backend- och databasinfrastruktur. PostgreSQL tränar dig på serverdatabas, connection strings, användare, migrations, SQLAlchemy och produktionslik arkitektur.

Future consequence: Mer setup nu, men mindre omskrivning senare.

## Decision #3

Problem:
Project structure for Python code.

Options:

- Flat structure
- src layout

Chosen:
src layout

Reason:
Cleaner imports and fewer packaging issues.

Consequences:
Requires package configuration in pyproject.toml.