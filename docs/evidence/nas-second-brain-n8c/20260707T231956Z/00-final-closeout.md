# N8C-21 — NAS Redeploy / Final Evidence / Live Operator Validation — closeout

**Phase:** N8C-21 — the program-level final validation + redeploy-readiness gate for the completed NAS
second-brain N8C stack (N8C-1…N8C-20). **Validation + packaging + operator-proof ONLY** — not a feature
layer, no schema change, no execution, no deployment.

**Base commit:** `14a0613a` (N8C-20 quality evaluation).
**Branch:** `ops/nas-second-brain-n8c-21-final-validation-20260707T231956Z`.
**Commit posture:** implemented + validated + evidenced; **LEFT UNCOMMITTED** (per instruction).

## What N8C-21 delivers (all local, non-destructive)

- `tests/test_n8c_final_validation.py` — first consolidated assertion that a fresh DB migrates to head V111
  and carries EVERY N8C-owned table (V100…V111), idempotent, prior rows survive.
- `tests/test_n8c_mcp_tool_inventory_final.py` — all 13 read-only assistant groups present by name (78 tools),
  each independently gated, finality guard across every tool, denied raw tools blocked, `ai_outputs_card_upsert`
  the only write, `hb_mcp_status` advertises every group.
- `scripts/n8c-mcp-smoke.sh` — LOCAL read-only end-to-end smoke over a TEMP DB (representative read per group;
  zero writes; production DB / backend / tunnel untouched).
- `deploy/nas/scripts/validate-db.sh` — stale expected constants bumped to the V111 posture (schema 98→111,
  tables 505→548, objects 507→550). Read-only check; constants only (no logic/write/migration added).
- `docs/architecture/n8c-final-validation.md` — validation contract + operator redeploy command sequence +
  live LLM-client validation + redaction rules.

## What N8C-21 does NOT do

No deployment, no service restart, no production migration, no production-DB mutation, no Cloudflare
tunnel/exposure change, no credential rotation, no push/PR/merge. No new schema, no new feature, no execution,
no N8D, no `agent_bridge`, no live LLM/source-read. Those NAS actions are DOCUMENTED as operator commands and
STOP-and-report if they must be performed.

## Result

Head V111; 13 groups / 78 tools; finality guard clean; `ai_outputs_card_upsert` sole write. New validation
tests + smoke green; N8C MCP regression green; schedule 345 + forecasting 1166 green at the identical schema
head under N8C-20 (N8C-21 adds zero `src/` runtime change). Evidence redacted + redaction-check clean.
