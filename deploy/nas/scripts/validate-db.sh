#!/bin/sh
# validate-db.sh — read-only production DB posture check (no writes, no migrations).
#
# Uses personal-assistant-svc read-only SQLite access when sudo is available.
# Expected counts match PR A/N3 application-object semantics (see VIEWER_MODE.md).
#
# Usage (on NAS):
#   deploy/nas/scripts/validate-db.sh
set -eu

DB="${HB_DB_PATH:-/volume1/personal-assistant/app-support/db/hb-personal-assistant.sqlite}"
EXPECTED_SCHEMA="${HB_EXPECTED_SCHEMA:-98}"
EXPECTED_TABLE_COUNT="${HB_EXPECTED_TABLE_COUNT:-505}"
EXPECTED_VIEW_COUNT="${HB_EXPECTED_VIEW_COUNT:-2}"
EXPECTED_OBJECT_COUNT="${HB_EXPECTED_SCHEMA_OBJECT_COUNT:-507}"
SVC_USER="${HB_DB_SVC_USER:-personal-assistant-svc}"

if [ ! -f "$DB" ]; then
  echo "FAIL: DB not found: $DB" >&2
  exit 1
fi

_run_sql() {
  _sql="$1"
  if command -v sudo >/dev/null 2>&1; then
    sudo -u "$SVC_USER" sqlite3 "file:${DB}?mode=ro" "$_sql" 2>/dev/null && return 0
  fi
  sqlite3 "file:${DB}?mode=ro" "$_sql"
}

echo "== validate-db (read-only) =="
echo "db=$DB"

_qc="$(_run_sql 'PRAGMA quick_check;')"
echo "quick_check=$_qc"
[ "$_qc" = "ok" ] || { echo "FAIL: quick_check != ok" >&2; exit 1; }

_schema="$(_run_sql 'SELECT MAX(version) FROM schema_migrations;')"
echo "schema=$_schema"
[ "$_schema" = "$EXPECTED_SCHEMA" ] || {
  echo "FAIL: schema=$_schema expected=$EXPECTED_SCHEMA" >&2
  exit 1
}

_tables="$(_run_sql "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")"
_views="$(_run_sql "SELECT COUNT(*) FROM sqlite_master WHERE type='view' AND name NOT LIKE 'sqlite_%';")"
_objects=$((_tables + _views))
echo "table_count=$_tables view_count=$_views schema_object_count=$_objects"

[ "$_tables" = "$EXPECTED_TABLE_COUNT" ] || {
  echo "FAIL: table_count=$_tables expected=$EXPECTED_TABLE_COUNT" >&2
  exit 1
}
[ "$_views" = "$EXPECTED_VIEW_COUNT" ] || {
  echo "FAIL: view_count=$_views expected=$EXPECTED_VIEW_COUNT" >&2
  exit 1
}
[ "$_objects" = "$EXPECTED_OBJECT_COUNT" ] || {
  echo "FAIL: schema_object_count=$_objects expected=$EXPECTED_OBJECT_COUNT" >&2
  exit 1
}

_stat="$(ls -la "$DB" 2>/dev/null || sudo ls -la "$DB" 2>/dev/null || true)"
echo "file_stat=$_stat"
case "$_stat" in
  *personal-assistant-svc*users*) echo "owner_ok=yes" ;;
  *) echo "WARN: expected owner personal-assistant-svc:users" ;;
esac
case "$_stat" in
  *" -rw------- "*) echo "mode_ok=yes (600)" ;;
  *) echo "WARN: expected mode 600 (-rw-------)" ;;
esac

echo "PASS: read-only DB validation"
