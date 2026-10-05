# syntax=docker/dockerfile:1.6
# ---------------------------------------------------------------------------
# Base: Python 3.12, ffmpeg, non-root user `app` with the host's UID/GID so
# nothing written to the bind mount is ever root-owned.
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS base

ARG UID=1000
ARG GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_CACHE_DIR=/opt/pipcache \
    PIP_DEFAULT_TIMEOUT=100 \
    PIP_RETRIES=8 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libmagic1 curl postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create the runtime user with the requested ids (re-use an existing group id if present)
RUN (getent group ${GID} || groupadd -g ${GID} app) \
    && useradd -m -u ${UID} -g ${GID} -s /bin/bash app || true \
    && mkdir -p /opt/venv /opt/pipcache /app \
    && chown -R ${UID}:${GID} /opt/venv /opt/pipcache /app

WORKDIR /app
COPY --chown=${UID}:${GID} requirements.txt requirements-dev.txt entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh && sed -i 's/\r$//' /app/entrypoint.sh

USER ${UID}:${GID}
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --upgrade pip

# ---------------------------------------------------------------------------
# dev: installs runtime + dev requirements; the entrypoint re-installs on start
# ---------------------------------------------------------------------------
FROM base AS dev
RUN /opt/venv/bin/pip install -r /app/requirements.txt -r /app/requirements-dev.txt
COPY --chown=${UID}:${GID} . /app
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "app", "--reload-dir", "engine"]

# ---------------------------------------------------------------------------
# prod: runtime requirements only, no reload, gunicorn with uvicorn workers
# ---------------------------------------------------------------------------
FROM base AS prod
ENV APP_ENV=production \
    SKIP_PIP_INSTALL=1
RUN /opt/venv/bin/pip install -r /app/requirements.txt
COPY --chown=${UID}:${GID} . /app
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "-w", "3", "-b", "0.0.0.0:8000", "--timeout", "120"]
