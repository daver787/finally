#!/usr/bin/env bash
# Start the FinAlly container (macOS / Linux). Idempotent.
set -euo pipefail

IMAGE_NAME="finally"
CONTAINER_NAME="finally"
URL="http://localhost:8000"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Already running? Just report and exit.
if docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  echo "FinAlly is already running at $URL"
  exit 0
fi

# Remove a stopped container of the same name so the run below succeeds.
if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  echo "Removing stopped container..."
  docker rm "$CONTAINER_NAME" >/dev/null
fi

# Ensure a .env file exists (env_file / --env-file requires it).
if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
  echo "No .env found. Copying .env.example -> .env (edit it to add your API keys)."
  cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
fi

# Build the image if requested with --build or if it does not exist yet.
if [[ "${1:-}" == "--build" ]] || ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
  echo "Building FinAlly image..."
  docker build -t "$IMAGE_NAME" "$PROJECT_ROOT"
fi

echo "Starting FinAlly..."
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -v finally-data:/app/db \
  -p 8000:8000 \
  --env-file "$PROJECT_ROOT/.env" \
  "$IMAGE_NAME" >/dev/null

echo "FinAlly is running at $URL"

# Open the browser on macOS.
if command -v open >/dev/null 2>&1; then
  ( sleep 2 && open "$URL" ) &
fi
