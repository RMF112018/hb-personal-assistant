# N8C Final Validation & NAS Redeploy Readiness (N8C-21)

This document is the **validation contract** for the completed NAS second-brain N8C program (N8C-1…N8C-20) and
the **operator runbook** for redeploying it to the Synology NAS. It performs no deployment itself: every
production action below is a command the operator runs — this repo only ships and validates the scaffolding.

## 1. Program state (commit lineage)

| phase | subject | commit |
|-------|---------|--------|
| N8C-17 | Core workflow context handlers | `0eb3ccb4` |
| N8C-18 | Feedback / review-loop (V109) | `c2022562` |
| N8C-19 | Action staging, not execution (V110) | `621e09b6` |
| N8C-20 | Quality / evaluation (V111) | `14a0613a` |
| N8C-21 | Final validation / redeploy readiness | *this branch (uncommitted)* |

Schema head: **V111**. MCP surface: **13 read-only assistant tool groups / 78 tools**; the only sanctioned
remote write is `ai_outputs_card_upsert`.

## 2. Validation contract (all local, non-destructive)

Run these locally (Mac or NAS) before redeploying. None touches the production DB, backend, or tunnel.

```sh
# a) schema + all-N8C-table posture (fresh temp DB → head 111, every N8C table present, idempotent)
pytest tests/test_n8c_final_validation.py -q

# b) full MCP inventory (13 groups / 78 tools, each independently gated, finality guard, denied raw tools,
#    ai_outputs is the only write tool, hb_mcp_status advertises every group)
pytest tests/test_n8c_mcp_tool_inventory_final.py -q

# c) end-to-end read-only MCP smoke over a TEMP DB (representative read per group; zero writes)
scripts/n8c-mcp-smoke.sh
```

Data-plane invariant: the internet-facing MCP **never** touches the live production DB. It reads a
checkpointed, read-only SNAPSHOT (`mode=ro&immutable=1` + `PRAGMA query_only=ON`). Every assistant tool is
served from that snapshot; there is no live-DB fallback and no remote write path other than
`ai_outputs_card_upsert`.

## 3. DB posture check on the NAS (read-only)

`deploy/nas/scripts/validate-db.sh` is a **read-only** posture check (`PRAGMA quick_check` + `MAX(version)` +
object counts; no writes, no migrations). Its expected constants were bumped for the N8C stack:

| constant | value (head V111) | override env |
|----------|-------------------|--------------|
| `EXPECTED_SCHEMA` | 111 | `HB_EXPECTED_SCHEMA` |
| `EXPECTED_TABLE_COUNT` | 548 | `HB_EXPECTED_TABLE_COUNT` |
| `EXPECTED_VIEW_COUNT` | 2 | `HB_EXPECTED_VIEW_COUNT` |
| `EXPECTED_SCHEMA_OBJECT_COUNT` | 550 | `HB_EXPECTED_SCHEMA_OBJECT_COUNT` |

These are the deterministic fresh-migrate counts (all objects are DDL, so a production DB migrated to the same
head matches). Run on the NAS: `deploy/nas/scripts/validate-db.sh`.

## 4. Operator redeploy command sequence (run ON THE NAS — not performed by this repo)

> The steps below are **documented commands the operator runs**. This phase does not restart services, run
> migrations, mutate the production DB, change the Cloudflare tunnel/exposure, rotate credentials, push, or
> deploy. STOP and hand off if any step needs those.

1. **Snapshot the read-only DB** the MCP reads (never the live 4 GB DB directly):
   `deploy/nas/scripts/snapshot-mcp-db.sh`
2. **Validate DB posture** (read-only): `deploy/nas/scripts/validate-db.sh`
   (expects schema 111 / 548 tables / 550 objects).
3. **Redeploy the MCP container** via the runner verbs: `deploy/nas/mcp/hb-mcp-runner stop` →
   `… start` → `… status` → `… health`. (Migrations, if any, are applied by the app's own startup path on the
   app-support DB — never by this validation flow.)
4. **Prove the OAuth origin** end-to-end against loopback BEFORE touching the edge:
   `deploy/nas/scripts/probe-oauth-origin.sh` (throwaway client, short-lived read-only token, `tools/list`).
5. **Edge / tunnel**: only if unchanged, leave as-is. Any Cloudflare tunnel/exposure or credential change is an
   explicit, separately-authorized operator action — out of scope here.

See `deploy/nas/mcp/README.md` and `deploy/nas/mcp/N8B-oauth-stage-b-runbook.md` for the full runbook.

## 5. Live LLM-client validation (bounded + redacted)

After redeploy, validate from a live MCP client (e.g. Claude/Grok remote MCP over the tunnel) using only
**read-only** tools and **bounded, redacted** evidence:

- Call `hb_mcp_status` → confirm all 13 assistant groups enabled + their tool lists.
- Call one representative read per new group (`assistant_list_action_stages`, `assistant_list_quality`, a
  workflow route) → confirm bounded advisory results.
- Confirm no write/build/apply/evaluate/repair tool is offered; confirm `ai_outputs_card_upsert` is the only
  write.

**Evidence redaction rules:** capture only tool names, counts, and status booleans. Never capture raw private
prompts, raw MCP payloads with private data, full source/file contents, raw email bodies, credentials, tunnel
tokens, or unbounded DB/private paths. Redacted evidence must pass
`scripts/obsidian_evidence_redaction_check.py <dir>`.
