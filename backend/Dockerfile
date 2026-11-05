# syntax=docker/dockerfile:1

# ==========================================================================
# Senobar — Django / DRF, served by Gunicorn
# ==========================================================================

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# libpq for psycopg, and curl for the healthcheck. Build tools go in the
# builder stage only, so they never reach the runtime image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 curl \
    && rm -rf /var/lib/apt/lists/*


# --- Builder: compile wheels ----------------------------------------------
FROM base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt gunicorn


# --- Runtime --------------------------------------------------------------
FROM base AS runtime

# Install from the prebuilt wheels: no compiler in the final image.
COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels /wheels/* && rm -rf /wheels

# Run as a non-root user.
RUN useradd --create-home --uid 1000 senobar

COPY --chown=senobar:senobar . .

# Writable paths for uploads and collected static files.
RUN mkdir -p /app/media /app/staticfiles && chown -R senobar:senobar /app

USER senobar

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health/ || exit 1

# 2 workers per core is the usual starting point; tune with WEB_CONCURRENCY.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--threads", "2", \
     "--timeout", "60", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
