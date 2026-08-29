# Same Page — production image.
# Python 3.12 + uv, single uvicorn worker (SQLite + boot-time Alembic migrations
# make multi-worker pure risk at this scale). Runs as a non-root user; the
# SQLite database lives on a mounted volume at $SP_DB_PATH, never in the image.

FROM python:3.12-slim

# uv for dependency install (matches local dev).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime deps first (cached until the lockfile changes).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# App code. alembic.ini + alembic/ must sit at the workdir root — the app runs
# `alembic upgrade head` from here at startup.
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Non-root. The mounted data volume must be writable by this uid (see compose).
RUN useradd --system --uid 10001 --home-dir /app samepage \
    && mkdir -p /data \
    && chown -R samepage:samepage /app /data
USER samepage

# The DB lives on the volume, not the image.
ENV SP_DB_PATH=/data/samepage.db \
    SP_PORT=8000 \
    SP_ENV=production
VOLUME ["/data"]
EXPOSE 8000

# Single worker on purpose (see header). --proxy-headers so the app trusts the
# reverse proxy's X-Forwarded-Proto/-For; --forwarded-allow-ips is set at run
# time to the proxy's address (compose passes the internal network).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
