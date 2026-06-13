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

Pending

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