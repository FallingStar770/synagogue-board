#!/bin/sh
set -e
# apply database migrations, ensure base data (+ admin from ADMIN_USERNAME/ADMIN_PASSWORD on first run)
alembic upgrade head
python -m app.cli seed-base
python - <<'PY'
from app.db import SessionLocal
from app.seed import bootstrap_admin_from_env
with SessionLocal() as db:
    bootstrap_admin_from_env(db)
PY
if [ "${SEED_DEMO:-false}" = "true" ]; then python -m app.cli seed-demo; fi
# only the web container can reach the API, so forwarded headers from it are trusted (real client IP for rate limiting)
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*' --workers 1
