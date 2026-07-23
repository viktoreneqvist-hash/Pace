"""Shared test configuration.

Tests use an isolated in-memory SQLite database and therefore never touch the
local development database at ``data/pace.db``.
"""

import os


os.environ.setdefault("PACE_DATABASE_URL", "sqlite+pysqlite:///:memory:")
