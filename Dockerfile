# syntax=docker/dockerfile:1

# Stage 1: Build the Next.js static export
FROM node:20-slim AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python backend serving the API and static frontend
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# curl is used by the container HEALTHCHECK
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies from the lockfile (production only)
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev

# Copy backend source
COPY backend/ .

# Copy the frontend static export produced in stage 1
COPY --from=frontend-builder /build/frontend/out ./static

# Runtime directory for the SQLite database (volume mount target)
RUN mkdir -p /app/db

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
  CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
