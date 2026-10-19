#!/bin/zsh
# Start Pace locally from Finder. Nothing is hosted or shared.
set -euo pipefail

cd "$(dirname "$0")"

UV_BIN="$(command -v uv || true)"
if [[ -z "$UV_BIN" ]]; then
  for candidate in /opt/homebrew/bin/uv /usr/local/bin/uv; do
    if [[ -x "$candidate" ]]; then
      UV_BIN="$candidate"
      break
    fi
  done
fi

if [[ -z "$UV_BIN" ]]; then
  printf '%s\n' "Pace needs uv to prepare and launch its local environment."
  printf '%s\n' "Install uv with Homebrew using: brew install uv"
  printf '%s\n' "Then double-click Start Pace.command again."
  if command -v osascript >/dev/null 2>&1; then
    choice="$(osascript -e 'display dialog "Pace needs uv before it can start. Install it with Homebrew (brew install uv), then open Pace again." buttons {"Open install guide", "OK"} default button "Open install guide" with title "Pace setup"')"
    if [[ "$choice" == *"Open install guide"* ]]; then
      open "https://docs.astral.sh/uv/getting-started/installation/"
    fi
  fi
  exit 1
fi

printf '%s\n' "Preparing Pace's local environment…"
if ! "$UV_BIN" sync; then
  printf '%s\n' "Pace could not prepare its environment. Review the message above, then try again."
  if command -v osascript >/dev/null 2>&1; then
    osascript -e 'display alert "Pace could not finish setup. Check the Terminal window for details, then try launching again." as warning with title "Pace setup"'
  fi
  exit 1
fi

printf '%s\n' "Starting Pace on this computer. Keep this window open while using Pace."
"$UV_BIN" run pace serve
