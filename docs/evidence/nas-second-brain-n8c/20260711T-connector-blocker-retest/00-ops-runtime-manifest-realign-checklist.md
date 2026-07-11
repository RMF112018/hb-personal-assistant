# Ops checklist — runtime ↔ client-tool-manifest realignment

**Disposition context:** Connector re-test **BLOCKED** — runtime/manifest drift active.

| Field | Observed value |
| --- | --- |
| Live runtime commit | `fc36311e64a63e9506ca624a4536423c2afa48d9` |
| Manifest `generated_from_runtime_commit` | `542307fc6fc87b7a5713b8917e861a576a03c96c` |
| Package | `1.3.0` |
| Manifest version (observed) | `9` |
| Live tool count | `145` manifested / `87` direct assistant |

**Goal:** Make tool-surface freshness and client-manifest freshness agree, with both
reporting **not stale** for deployment-runtime identity (tool-name drift is separate).

**Authorization:** Steps that **stage/promote** the client tool manifest or **redeploy** the
container require explicit operator approval. This document is a checklist only; do not
run promote/deploy steps without that approval.

---

## A. Read-only diagnosis (safe; no writes)

Run against the live NAS MCP (host or container). Capture JSON for evidence.

1. **Runtime identity**
   - Call `hb_mcp_status` (or broker `runtime_commit()`).
   - Record: `runtime_commit`, package, image digest, safe mode.

2. **Surface freshness**
   - Call `pa_tool_surface_freshness_check`.
   - Expect while misaligned: `staleness_state: stale`, `deployment_runtime_drift: true`,
     warning `deployment_runtime_commit_mismatch`, `review_required: true`.

3. **Manifest freshness**
   - Call `pa_tool_manifest_freshness_check`.
   - **Before code fix (runtime `fc36311e` without P0 freshness patch):** may still report
     `fresh` if tool **names** match — this is the dual-surface defect.
   - **After P0 freshness patch is deployed:** must report stale when
     `generated_from_runtime_commit` ≠ live runtime SHA
     (`staleness_state: deployment_runtime_commit_mismatch`).

4. **Active manifest header**
   - Call `pa_tool_manifest_get` (persisted).
   - Record: `manifest_version`, `generated_from_runtime_commit`, `checksum`,
     `tool_count`, `workflow_count`, `manifest_status`.

5. **Pass criteria for “aligned”**
   - Live runtime commit == active manifest `generated_from_runtime_commit`
   - `pa_tool_surface_freshness_check.stale == false` for deployment-runtime category
     (other categories may still flag independent defects)
   - `pa_tool_manifest_freshness_check.tool_manifest_stale == false`
   - `hb_mcp_status` does not report contradictory fresh/stale pair for the same identity

---

## B. Preferred realignment (keep current runtime `fc36311e…`)

Use when the **running image/commit is correct** and only the **persisted manifest** is old.

Requires: operator approval for **manifest stage + promote** (writes DB + vault materialization).

### B1. Preconditions

- Container `hb-personal-assistant-mcp` running.
- Runtime commit already equals the target SHA (here: `fc36311e…`).
- Schema index frozen / manifest schema parity OK (stage fails closed otherwise).
- Safe mode off if promote requires full tool surface (follow site policy).

### B2. Stage refresh (server-minted approval)

On NAS as root (pattern from prior deploy evidence
`docs/evidence/nas-second-brain-n8c/20260711T-prod-readiness-p0-p1/02-manifest-refresh.sh`):

```sh
# AUTHORIZATION REQUIRED — stages a refresh proposal (DB write)
DOCKER=/usr/local/bin/docker
CONTAINER=hb-personal-assistant-mcp

$DOCKER exec "$CONTAINER" python3 -c '
import json
from mcp.server.fastmcp import FastMCP
from hb_assistant.nas_mcp.broker import NasMcpBroker, runtime_commit
from hb_assistant.nas_mcp.config import NasMcpConfig
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
cfg = NasMcpConfig.from_env()
b = NasMcpBroker(cfg)
register_nas_mcp_tools(FastMCP("hb-nas-mcp", json_response=True, stateless_http=True), b)
print("runtime_commit=", runtime_commit())
r = b.dispatch("pa_tool_manifest_refresh_stage", {})
print(json.dumps(r, indent=2, sort_keys=True))
'
```

Capture from result:

- `refresh_proposal_id`
- `operator_approval_id` (server-minted; never invent)

Confirm staged manifest was built with `runtime_commit == fc36311e…`.

### B3. Promote (operator approval)

```sh
# AUTHORIZATION REQUIRED — promotes active manifest + vault paths
REFRESH_ID='…from stage…'
APPROVAL_ID='…from stage…'

$DOCKER exec "$CONTAINER" python3 -c "
import json
from mcp.server.fastmcp import FastMCP
from hb_assistant.nas_mcp.broker import NasMcpBroker
from hb_assistant.nas_mcp.config import NasMcpConfig
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
cfg = NasMcpConfig.from_env()
b = NasMcpBroker(cfg)
register_nas_mcp_tools(FastMCP('hb-nas-mcp', json_response=True, stateless_http=True), b)
r = b.dispatch('pa_tool_manifest_refresh_promote', {
  'refresh_proposal_id': '$REFRESH_ID',
  'operator_approval_id': '$APPROVAL_ID',
})
print(json.dumps(r, indent=2, sort_keys=True))
"
```

### B4. Verify (read-only)

```sh
$DOCKER exec "$CONTAINER" python3 -c '
import json
from mcp.server.fastmcp import FastMCP
from hb_assistant.nas_mcp.broker import NasMcpBroker, runtime_commit
from hb_assistant.nas_mcp.config import NasMcpConfig
from hb_assistant.nas_mcp.tool_registration import register_nas_mcp_tools
cfg = NasMcpConfig.from_env()
b = NasMcpBroker(cfg)
register_nas_mcp_tools(FastMCP("hb-nas-mcp", json_response=True, stateless_http=True), b)
rc = runtime_commit()
m = b.dispatch("pa_tool_manifest_get", {})["result"]
mf = b.dispatch("pa_tool_manifest_freshness_check", {})["result"]
sf = b.dispatch("pa_tool_surface_freshness_check", {})["result"]
out = {
  "runtime_commit": rc,
  "manifest_generated_from": m.get("generated_from_runtime_commit"),
  "manifest_version": m.get("manifest_version"),
  "manifest_stale": mf.get("tool_manifest_stale"),
  "manifest_staleness_state": mf.get("staleness_state"),
  "manifest_deployment_runtime_drift": mf.get("deployment_runtime_drift"),
  "surface_stale": sf.get("stale"),
  "surface_staleness_state": sf.get("staleness_state"),
  "surface_deployment_runtime_drift": (sf.get("categories") or {}).get("deployment_runtime_drift"),
}
print(json.dumps(out, indent=2, sort_keys=True))
assert m.get("generated_from_runtime_commit") == rc
assert mf.get("tool_manifest_stale") is False
assert mf.get("deployment_runtime_drift") is not True
'
```

Save stdout under this evidence directory as `01-post-realign-freshness.json`.

---

## C. Alternate realignment (redeploy runtime to match old manifest)

Use only if the **desired** runtime is the manifest’s SHA (`542307fc…`), not `fc36311e…`.

1. Explicit **deploy authorization** required.
2. Build/deploy image with `HB_BUILD_SHA` / `HB_RUNTIME_COMMIT` set to the **deployed** commit.
3. Confirm `runtime_commit()` equals that SHA.
4. Re-run section A. Manifest regen may still be required if tool surface changed after `542307fc`.

**Do not** claim alignment if only one of {image stamp, env SHA, persisted manifest} matches.

---

## D. Source-index health DB path (related blocker; separate from manifest)

Observed failure:

```text
Database unavailable at
/volume2/personal-assistant/app-support/mcp-snapshot/db/hb-personal-assistant.sqlite
```

Read-only checks (no mutations):

1. Confirm path exists and is readable inside the container.
2. Confirm `NasMcpConfig` / env points snapshot and primary DB as intended.
3. Confirm `assistant_source_index_health` remains gateway-callable and returns a structured
   unavailable envelope rather than a hard gateway failure (code path improvements land in
   later PRs; env fix may be sufficient for data plane).

**Do not** rebuild indexes as part of “certify all tools” without a cleanup plan.

---

## E. What this checklist does **not** authorize

- Container image rebuild/redeploy
- Indexing, archival, or canonical promotion
- Forging `operator_approval_id`
- Lowering production-readiness score based on incomplete “all tools” coverage

---

## F. Ordering with code P0

| Order | Action |
| --- | --- |
| 1 | Ship/deploy code P0 (typed IDs, negation, manifest freshness runtime-commit) — **separate deploy approval** |
| 2 | Run **B** (or **C**) so persisted manifest matches live runtime |
| 3 | Re-run connector subset: PROMOB exact ID, staged-actions negation, dual freshness agree |
| 4 | Only then resume broader certification / attestation |

Until (1)+(2) complete, disposition remains **CONNECTOR_BLOCKER_FOUND**.
