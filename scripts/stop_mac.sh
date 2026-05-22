#!/usr/bin/env bash
# Stop and remove the FinAlly container (macOS / Linux). Idempotent.
# The finally-data volume is preserved so the database survives restarts.
set -euo pipefail

CONTAINER_NAME="finally"

if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  echo "Stopping FinAlly..."
  docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
  docker rm "$CONTAINER_NAME" >/dev/null
  echo "Stopped. (The finally-data volume was kept.)"
else
  echo "FinAlly is not running."
fi
