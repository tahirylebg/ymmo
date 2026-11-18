#!/bin/sh
# Ymmo - local dump of the platform (SRV-AIX-02), picked up by the NAS backup agent.
#   ymmo-backup-db.sh        PostgreSQL dump (hourly, working hours)
#   ymmo-backup-db.sh full   PostgreSQL dump + uploaded media (nightly)
# A logical dump (pg_dump) is consistent while the database runs; copying the raw volume is not.
# On success, touches $DEST/last_success: the supervision alerts when it gets too old.
set -eu

APP_DIR=${APP_DIR:-/opt/ymmo}
DEST=${DEST:-/var/backups/ymmo}
KEEP_DAYS=${KEEP_DAYS:-14}
stamp=$(date +%Y-%m-%d_%H%M)

umask 077
mkdir -p "$DEST"
rm -f "$DEST"/*.part
cd "$APP_DIR"

# Credentials come from the db container's own environment (no secret in this script)
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
    > "$DEST/db_$stamp.dump.part"
test -s "$DEST/db_$stamp.dump.part"
mv "$DEST/db_$stamp.dump.part" "$DEST/db_$stamp.dump"

if [ "${1:-}" = full ]; then
    docker compose exec -T app tar -C /app -czf - media > "$DEST/media_$stamp.tar.gz.part"
    mv "$DEST/media_$stamp.tar.gz.part" "$DEST/media_$stamp.tar.gz"
fi

# Local retention only: the NAS keeps the long history
find "$DEST" -maxdepth 1 \( -name 'db_*.dump' -o -name 'media_*.tar.gz' \) -mtime +"$KEEP_DAYS" -delete
touch "$DEST/last_success"
echo "ymmo-backup: OK $stamp ${1:-db}"
