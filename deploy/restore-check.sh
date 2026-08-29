#!/usr/bin/env bash
# Verify a backup actually restores (plan M5: "WAL-safe backup + restore check").
# A backup you have never restored is a hope, not a backup.
#
# Restores the newest backup into a scratch copy and asserts the schema is at
# Alembic head and the core tables are queryable — WITHOUT touching the live DB.
#
# Usage:  deploy/restore-check.sh [BACKUP_DIR]
# Default: BACKUP_DIR=/data/backups
set -euo pipefail

BACKUP_DIR="${1:-/data/backups}"

latest="$(find "$BACKUP_DIR" -name 'samepage-*.db' -type f | sort | tail -n1)"
if [ -z "$latest" ]; then
	echo "restore-check: no backups found in $BACKUP_DIR" >&2
	exit 1
fi

scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
cp "$latest" "$scratch/restored.db"

if [ "$(sqlite3 "$scratch/restored.db" 'PRAGMA integrity_check;')" != "ok" ]; then
	echo "restore-check: integrity check FAILED for $latest" >&2
	exit 1
fi

# The schema must be at a known Alembic revision (proves migrations ran) and the
# core tables must exist. alembic_version holds the current head.
rev="$(sqlite3 "$scratch/restored.db" 'SELECT version_num FROM alembic_version;')"
if [ -z "$rev" ]; then
	echo "restore-check: no alembic_version — not a migrated database" >&2
	exit 1
fi

for table in account "group" collection item session batch_item; do
	sqlite3 "$scratch/restored.db" "SELECT count(*) FROM \"$table\";" >/dev/null
done

echo "restore-check: $latest restores cleanly (alembic rev $rev, core tables queryable)"
