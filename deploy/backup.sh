#!/usr/bin/env bash
# WAL-safe backup of the Same Page SQLite database.
#
# Uses `sqlite3 .backup`, NOT a raw cp: the DB runs in WAL mode, so a plain
# copy of the .db file can miss committed pages still in the -wal sidecar and
# produce a torn/inconsistent backup. `.backup` takes a consistent snapshot of
# a live database.
#
# Usage:  deploy/backup.sh [DB_PATH] [BACKUP_DIR]
# Defaults: DB_PATH=/data/samepage.db  BACKUP_DIR=/data/backups
# Cron example (daily 03:17):  17 3 * * *  /app/deploy/backup.sh
set -euo pipefail

DB_PATH="${1:-/data/samepage.db}"
BACKUP_DIR="${2:-/data/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if [ ! -f "$DB_PATH" ]; then
	echo "backup: no database at $DB_PATH" >&2
	exit 1
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
dest="$BACKUP_DIR/samepage-$stamp.db"

# Consistent snapshot of the live WAL-mode DB.
sqlite3 "$DB_PATH" ".backup '$dest'"
chmod 600 "$dest"

# Integrity-check the snapshot before trusting it.
if [ "$(sqlite3 "$dest" 'PRAGMA integrity_check;')" != "ok" ]; then
	echo "backup: integrity check FAILED for $dest" >&2
	exit 1
fi

# Prune old backups.
find "$BACKUP_DIR" -name 'samepage-*.db' -type f -mtime "+$RETENTION_DAYS" -delete

echo "backup: wrote $dest ($(du -h "$dest" | cut -f1)), integrity ok"
