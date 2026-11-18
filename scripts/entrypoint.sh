#!/bin/sh
# Container entrypoint: apply migrations, optionally seed demo data, then start the server.
set -e

echo "[entrypoint] Applying database migrations..."
alembic upgrade head

if [ "${SEED_ON_STARTUP:-false}" = "true" ] && [ -f scripts/seed.py ]; then
    echo "[entrypoint] Seeding demo data (skipped automatically if already present)..."
    python -m scripts.seed
    echo "[entrypoint] Illustrating listings without photo (CC0 images, see docs/photos-libres.md)..."
    python -m scripts.illustration_photos add || echo "[entrypoint] Illustration photos skipped."
    echo "[entrypoint] Training the price model (skipped if already trained)..."
    python -m analytics.train --if-missing || echo "[entrypoint] Model training skipped."
fi

exec "$@"
