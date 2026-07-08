#!/bin/sh
# Fold the internet-facing MCP's writable WORKSPACE DB back into the authoritative live DB.
#
# WHY: the internet-facing MCP reads a read-only snapshot and writes the connected-client STAGING
# pipeline (session capture → artifact proposal → review → promotion, generated-output stage/commit,
# tool-manifest refresh) to an ISOLATED writable workspace DB
# (/volume2/personal-assistant/app-support/mcp-workspace/db/hb-personal-assistant.sqlite). Those rows
# are durable but live apart from the authoritative DB the snapshot is taken from. This job is the
# opposite direction of snapshot-mcp-db.sh: it merges promoted workspace rows into the live DB so the
# authoritative second brain sees them.
#
# STATUS: DESIGN STUB — NOT YET WIRED. Deliberately refuses to run so no half-designed merge can
# corrupt the live DB. Implement the row-level reconcile below (idempotent, promoted-only, conflict
# policy) and remove the guard before scheduling.
#
# DESIGN (to implement):
#   * Source: workspace DB (RW mount). Target: live DB $APP_SUPPORT/db/hb-personal-assistant.sqlite.
#   * Scope: PROMOTED/committed rows only — pa_canonical_artifacts (status='canonical'),
#     pa_promotion_receipts, committed assistant_output_files + manifest/receipt rows, and the
#     active pa_client_tool_manifests set. Never copy in-flight staged/proposed rows.
#   * Idempotent: key on server-minted ids (canonical_id / promotion_receipt_id / output_id /
#     manifest checksum); INSERT-OR-IGNORE + a merge ledger so re-runs are no-ops.
#   * Conflict policy: a workspace canonical id that already exists live is a no-op (the workspace is
#     downstream); log divergences, never overwrite authoritative rows.
#   * Safety: take a live-DB backup first (SQLite online backup), operate inside a single transaction,
#     run local/operator-only (never internet-exposed), and record a receipt under audit/mcp.
#
# RUN (operator, once implemented): sudo sh deploy/nas/scripts/merge-workspace-to-live.sh
set -eu

echo "merge-workspace-to-live.sh is a DESIGN STUB and is not yet implemented." >&2
echo "See the header for the intended row-level, promoted-only, idempotent merge design." >&2
echo "Refusing to run to protect the authoritative live DB." >&2
exit 2
