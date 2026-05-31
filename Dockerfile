# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1 — frontend builder
# Builds the Next.js static export (output: "export" -> /build/out).
# Used only as a COPY source for the runtime stage.
# ---------------------------------------------------------------------------
# Base images pinned by immutable digest (not floating tags) for reproducible,
# supply-chain-verified builds. Refresh digests deliberately when bumping versions.
FROM node:20-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0 AS frontend
WORKDIR /build

# Copy lockfiles first so `npm ci` is cached when only source changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy the rest of the frontend and produce the static export.
COPY frontend/ ./
RUN npm run build
# Result: /build/out contains the static Next.js export.

# ---------------------------------------------------------------------------
# Stage 2 — runtime (final image, default target)
#
# Container layout (WORKDIR /app):
#   /app/backend/            <- copy of backend/ (so main.py lands at
#                               /app/backend/app/main.py)
#   /app/backend/static/     <- copy of frontend/out (FastAPI computes the
#                               static dir as Path(__file__).parent.parent /
#                               "static" = /app/backend/app/.. / static)
#   /app/db/                 <- VOLUME mount target for named volume finally-data
#
# Option A from the plan: copying backend/ to /app/backend/ keeps the existing
# main.py path logic intact without code changes. For main.py at
# /app/backend/app/main.py, _project_root = parent.parent.parent = /app, so
# _default_db = /app/db/finally.db — matches the documented volume mount.
#
# NOTE: .env is intentionally NOT copied. Use --env-file at run time.
# ---------------------------------------------------------------------------
FROM python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install uv deterministically via image-based delivery (no curl | sh).
# Pinned to an exact uv version AND immutable digest: a floating :latest tag
# would let two builds of the same committed source install different uv
# binaries, defeating the `uv sync --frozen` reproducibility guarantee and
# allowing an upstream tag change to be injected unverified.
COPY --from=ghcr.io/astral-sh/uv:0.9.2@sha256:6dbd7c42a9088083fa79e41431a579196a189bcee3ae68ba904ac2bf77765867 /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy dependency manifests first so the dependency-resolution layer is cached
# when only application source changes. README.md is required because the
# project's build backend (hatchling) reads it as the long description.
COPY backend/pyproject.toml backend/uv.lock backend/README.md /app/backend/

# Install dependencies from the committed lockfile only (no project, no dev).
# Splitting deps from the project install keeps the heavy dep layer cached.
RUN cd /app/backend && uv sync --frozen --no-dev --no-install-project

# Copy the backend source (gives /app/backend/app/main.py, etc.).
COPY backend/ /app/backend/

# Copy the Next.js static export from Stage 1 into FastAPI's static dir.
COPY --from=frontend /build/out /app/backend/static

# Install the project itself into the venv now that source is present.
RUN cd /app/backend && uv sync --frozen --no-dev

# Non-root runtime user (UID 10001) owns /app and /app/db so init_db can
# create /app/db/finally.db on first start without root.
RUN groupadd -r app && useradd -r -u 10001 -g app -d /home/app -m -s /bin/bash app \
    && mkdir -p /app/db \
    && chown -R app:app /app /home/app

# Declarative metadata for the persistence path (named volume mounts here).
VOLUME ["/app/db"]

USER app
WORKDIR /app/backend
EXPOSE 8000

# uvicorn lives in the uv-managed venv; put it on PATH.
ENV PATH="/app/backend/.venv/bin:$PATH"

# start-period covers DB init + market-data startup before the server is ready.
# healthcheck.py (at WORKDIR /app/backend) maps any probe failure to a clean
# non-zero exit without a traceback.
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD ["python", "healthcheck.py"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
