#!/usr/bin/env bash
set -euo pipefail

# start_mac.sh — Launch the FinAlly Docker container (macOS / Linux).
#
# Builds the `finally` image if it is missing (or if --build is passed),
# starts a detached container with the persistent named volume, the env-file,
# and the port mapping, waits for the container HEALTHCHECK to report healthy,
# then prints the access URL.
#
# Idempotent: running it twice in a row detects an already-running healthy
# container and prints the URL without rebuilding or duplicating containers.

# --- Resolve repo root so the script works from any cwd -----------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# --- Constants (must match Plan 04-01 Dockerfile + planning/PLAN.md sec 11) ----
IMAGE=finally
CONTAINER=finally-app
VOLUME=finally-data
PORT=8000
URL="http://localhost:${PORT}"

# --- Parse a single optional flag: --build ------------------------------------
FORCE_BUILD=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --build)
      FORCE_BUILD=1
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [--build]"
      echo "  --build   Force a docker build even when the image already exists."
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument '$1'." >&2
      echo "Usage: $0 [--build]" >&2
      exit 2
      ;;
  esac
done

# --- Preflight: Docker daemon must be running ---------------------------------
docker info >/dev/null 2>&1 || { echo "ERROR: Docker is not running. Start Docker Desktop and retry." >&2; exit 1; }

# --- Preflight: .env presence (warn-only, never fatal) ------------------------
ENV_PRESENT=0
if [ -f "$REPO_ROOT/.env" ]; then
  ENV_PRESENT=1
else
  echo "WARNING: .env not found at $REPO_ROOT/.env — OPENROUTER_API_KEY will be unset; chat will fail. Copy .env.example to .env and add keys."
fi

# --- Image build logic --------------------------------------------------------
if [ "$FORCE_BUILD" -eq 1 ]; then
  docker build -t "$IMAGE" "$REPO_ROOT" || { echo "ERROR: docker build failed." >&2; exit 1; }
elif docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Using existing image $IMAGE (pass --build to rebuild)."
else
  docker build -t "$IMAGE" "$REPO_ROOT" || { echo "ERROR: docker build failed." >&2; exit 1; }
fi

# --- Idempotency: inspect any existing container ------------------------------
ALREADY_RUNNING=0
if docker inspect "$CONTAINER" >/dev/null 2>&1; then
  STATUS="$(docker inspect --format='{{.State.Status}}' "$CONTAINER" 2>/dev/null || echo unknown)"
  if [ "$STATUS" = "running" ]; then
    if [ "$FORCE_BUILD" -eq 1 ]; then
      # A forced rebuild must take runtime effect: replace the running container
      # so it picks up the freshly built image (otherwise --build is a no-op).
      docker rm -f "$CONTAINER" >/dev/null
    else
      ALREADY_RUNNING=1
    fi
  else
    # exited / created / paused / anything non-running: remove and re-run
    docker rm -f "$CONTAINER" >/dev/null
  fi
fi

# --- Start container (unless one is already running) --------------------------
if [ "$ALREADY_RUNNING" -eq 0 ]; then
  if [ "$ENV_PRESENT" -eq 1 ]; then
    docker run -d --name "$CONTAINER" -v "$VOLUME":/app/db -p "${PORT}:8000" --env-file "$REPO_ROOT/.env" "$IMAGE" >/dev/null \
      || { echo "ERROR: docker run failed (is port ${PORT} already in use?). Check: docker logs $CONTAINER" >&2; exit 1; }
  else
    docker run -d --name "$CONTAINER" -v "$VOLUME":/app/db -p "${PORT}:8000" "$IMAGE" >/dev/null \
      || { echo "ERROR: docker run failed (is port ${PORT} already in use?). Check: docker logs $CONTAINER" >&2; exit 1; }
  fi
fi

# --- Wait for healthy (max 60s, poll every 1s) -------------------------------
# 60s covers Docker's own HEALTHCHECK budget (start-period 20s + 5 retries x
# 10s interval) so a slow first boot is not misreported as a script timeout.
HEALTHY=0
i=0
while [ "$i" -lt 60 ]; do
  status="$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || echo unknown)"
  if [ "$status" = "healthy" ]; then
    HEALTHY=1
    break
  fi
  sleep 1
  i=$((i + 1))
done

if [ "$HEALTHY" -ne 1 ]; then
  echo "ERROR: container did not become healthy within 60s. Check logs: docker logs $CONTAINER" >&2
  exit 1
fi

# --- Success -----------------------------------------------------------------
echo "FinAlly is running."
echo "Open: $URL"
echo "Stop: ./scripts/stop_mac.sh"
exit 0
