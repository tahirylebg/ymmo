#!/bin/sh
# Container entrypoint: apply migrations, optionally seed demo data, then start the server.
set -e

echo "[entrypoint] Applying database migrations..."
alembic upgrade head

if [ "${SEED_ON_STARTUP:-false}" = "true" ] && [ -f scripts/seed.py ]; then
    echo "[entrypoint] Seeding demo data (skipped automatically if already present)..."
    python -m scripts.seed
fi

exec "$@"
