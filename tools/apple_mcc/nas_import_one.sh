#!/usr/bin/env bash
# Run ON NAS as personal-assistant-svc with HB_NAS_RUNTIME=1.
set -euo pipefail
ARCHIVE="${1:?archive required}"
shift || true
export HB_NAS_RUNTIME=1
export PYTHONPATH="${PYTHONPATH:-/volume2/personal-assistant/runtime/apple-mcc/src}"
DB="${HB_NAS_DB_PATH:-/volume2/personal-assistant/app-support/db/hb-personal-assistant.sqlite}"
exec python3 -m hb_assistant.apple_mcc.ops.nas_import_staged \
  --archive "$ARCHIVE" \
  --db "$DB" \
  "$@"
