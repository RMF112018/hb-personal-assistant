# HB Personal Assistant — NAS runtime image (Phase N1B scaffold)
# Builds the backend (FastAPI) for the analytics/api:create_app factory.
#
# SAFETY / SCOPE (N1B):
#   * No live DB, secrets, tokens, vault, or user config are baked in — see .dockerignore.
#   * Config is supplied ONLY at runtime via HB_PA_CONFIG (mounted read-only by compose).
#   * Background workers/watchers/schedulers are disabled by default env below.
#   * This Dockerfile is authored for review; do NOT build/run on the NAS without
#     separate operator authorization (Phase N1C).
#
# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

# Non-root runtime user mapped to the NAS runtime identity (personal-assistant-svc = 1028:100/users)
# so files written into the mounted app-support tree keep correct NAS ownership.
RUN set -eux; \
    (getent group 100 >/dev/null || groupadd --gid 100 hbusers); \
    useradd --uid 1028 --gid 100 --no-create-home --shell /usr/sbin/nologin hbsvc

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Runtime defaults — the actual config file is mounted read-only at /config by compose.
    HB_PA_CONFIG=/config/hb-pa-config.yml \
    HB_NAS_RUNTIME=1 \
    # Master kill switch: disables the quality-poll loop + source watcher + source-root
    # registration started by the app lifespan (see src/.../analytics/api.py:671-798).
    HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1

WORKDIR /app

# Copy the source tree (sensitive/heavy paths excluded via repo-root .dockerignore) and install
# the backend with the optional analytics-ui extra (fastapi>=0.115, uvicorn>=0.30 — pyproject.toml:96).
# If a future base image lacks wheels for a dep, add build deps here (build-essential) — omitted to keep
# the image lean; current deps ship manylinux wheels.
COPY . /app
# Normalize permissions so the non-root runtime user (USER hbsvc, below) can read/traverse the
# source tree regardless of the build-context's source perms. This matters when the context is
# staged by a copy/tar that preserves restrictive POSIX modes (e.g. 0700 dirs from an ACL-backed
# share) rather than a plain `git clone`. Read+traverse only; no write bits granted.
RUN chmod -R a+rX /app
RUN python -m pip install --upgrade pip \
 && python -m pip install -e ".[analytics-ui]"

EXPOSE 8000
USER hbsvc

# Backend factory command (repo-truth: src/hb_assistant/construction/analytics/api.py:781).
# 0.0.0.0 here binds only inside the container's network namespace; host exposure is controlled
# by the compose port publish (defaults to loopback — never the host's 0.0.0.0).
CMD ["python", "-m", "uvicorn", "hb_assistant.construction.analytics.api:create_app", \
     "--factory", "--host", "0.0.0.0", "--port", "8000"]
