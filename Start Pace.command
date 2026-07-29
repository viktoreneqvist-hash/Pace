#!/bin/zsh
# Start Pace locally from Finder. Nothing is hosted or shared.
set -euo pipefail

cd "$(dirname "$0")"
uv sync
exec uv run pace serve
