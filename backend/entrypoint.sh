#!/usr/bin/env bash
# Runs on every container start for api and worker.
#  1. install requirements into /opt/venv (a named volume shared by api and worker, guarded by a
#     lock; a fast no-op when nothing changed)
#  2. wait for the database
#  3. api only (RUN_MIGRATIONS=1): run migrations and the idempotent seed
#     worker (RUN_MIGRATIONS=0): wait until the api has applied the migrations
#  4. exec the service command
set -euo pipefail

export PATH="/opt/venv/bin:${PATH}"
APP_ENV="${APP_ENV:-local}"

if [ ! -x /opt/venv/bin/python ]; then
  echo "[entrypoint] creating virtualenv at /opt/venv"
  python -m venv /opt/venv
fi

if [ "${SKIP_PIP_INSTALL:-0}" != "1" ]; then
  echo "[entrypoint] installing requirements (APP_ENV=${APP_ENV})"
  (
    flock -w 600 9 || { echo "[entrypoint] could not acquire the pip lock" >&2; exit 1; }
    if [ "${APP_ENV}" = "local" ] || [ "${APP_ENV}" = "test" ]; then
      /opt/venv/bin/pip install --quiet -r /app/requirements.txt -r /app/requirements-dev.txt
    else
      /opt/venv/bin/pip install --quiet -r /app/requirements.txt
    fi
  ) 9>/opt/venv/.pip.lock
fi

echo "[entrypoint] waiting for database"
/opt/venv/bin/python - <<'PY'
import asyncio, os, sys, time
import asyncpg

url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
wait_for_schema = os.environ.get("RUN_MIGRATIONS", "0") != "1"
deadline = time.time() + 180


async def check() -> bool:
    conn = await asyncpg.connect(url)
    try:
        await conn.execute("SELECT 1")
        if wait_for_schema:
            row = await conn.fetchrow("SELECT to_regclass('public.alembic_version') AS t")
            if row is None or row["t"] is None:
                return False
            row = await conn.fetchrow("SELECT count(*) AS n FROM alembic_version")
            return bool(row and row["n"])
        return True
    finally:
        await conn.close()


while True:
    try:
        if asyncio.run(check()):
            print("[entrypoint] database is ready")
            break
        print("[entrypoint] waiting for migrations to be applied by the api container")
    except Exception as exc:  # noqa: BLE001
        if time.time() > deadline:
            print(f"[entrypoint] database not reachable: {exc}", file=sys.stderr)
            sys.exit(1)
    if time.time() > deadline:
        print("[entrypoint] timed out waiting for the database / migrations", file=sys.stderr)
        sys.exit(1)
    time.sleep(2)
PY

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "[entrypoint] running migrations"
  /opt/venv/bin/alembic upgrade head
  echo "[entrypoint] seeding"
  /opt/venv/bin/python -m scripts.seed
fi

echo "[entrypoint] starting: $*"
exec "$@"
