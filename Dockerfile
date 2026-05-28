# syntax=docker/dockerfile:1.7

# ---------- Builder stage ----------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Build deps only needed for compiling wheels (numpy/scikit-learn fallbacks).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Isolated virtualenv that we copy whole into the runtime image.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build

# Copy requirements first so this layer caches when only source changes.
COPY requirements.txt ./

# Install runtime deps. shap and matplotlib are listed in requirements.txt
# but are NOT imported by services/ or packages/, so we drop them here to
# keep the image lean (shap pulls llvmlite/numba; matplotlib pulls fonts).
RUN grep -viE '^(shap|matplotlib)([<>=!~ ]|$)' requirements.txt > /tmp/runtime-requirements.txt \
    && pip install --upgrade pip \
    && pip install -r /tmp/runtime-requirements.txt


# ---------- Runtime stage ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    MARKET_BOT_DB_PATH=/data/market_bot.db

# libgomp1 is required by scikit-learn's OpenMP-enabled wheels at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user owns /data so the Fly volume mount works without root.
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --create-home --home-dir /home/app app \
    && mkdir -p /data \
    && chown -R app:app /data

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Copy only what the API needs to run. We intentionally skip tests/, legacy/,
# data/, apps/web/, docs/ and other non-runtime trees via .dockerignore.
COPY --chown=app:app services ./services
COPY --chown=app:app packages ./packages

# services/api/app.py mounts StaticFiles from apps/web/prototype. Create an
# empty placeholder so Starlette's check_dir=True passes at startup even when
# the frontend is deployed elsewhere (Vercel).
RUN mkdir -p /app/apps/web/prototype && chown -R app:app /app/apps

USER app

EXPOSE 8080

CMD ["uvicorn", "services.api.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
