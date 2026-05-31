#!/usr/bin/env bash
set -euo pipefail

# stop_mac.sh — Stop and remove the FinAlly Docker container (macOS / Linux).
#
# Stops + removes the running container but NEVER touches the named volume,
# so all SQLite data (positions, trades, watchlist, chat history) persists and
# reloads on the next start. Idempotent: running it when no container exists
# exits 0 with an informational message rather than an error.

# --- Constants (must match start_mac.sh) -------------------------------------
CONTAINER=finally-app
VOLUME=finally-data

# --- Preflight: Docker daemon must be running --------------------------------
docker info >/dev/null 2>&1 || { echo "ERROR: Docker is not running." >&2; exit 1; }

# --- Idempotent stop ---------------------------------------------------------
# `docker rm -f` force-stops then removes in one call, avoiding the
# stop-succeeds-then-rm-against-running race; check the result so the
# volume-preserved reassurance is never printed after a failed removal.
if docker inspect "$CONTAINER" >/dev/null 2>&1; then
  docker rm -f "$CONTAINER" >/dev/null \
    && echo "Stopped and removed container $CONTAINER." \
    || { echo "ERROR: failed to remove $CONTAINER." >&2; exit 1; }
else
  echo "No container named $CONTAINER is running."
fi

# --- Volume preservation guard -----------------------------------------------
# The named volume is intentionally left untouched. This script must NEVER
# delete it — doing so would destroy all persistent user data (SCPT-02).
echo "Volume $VOLUME preserved. Data will reload on next start."
exit 0
