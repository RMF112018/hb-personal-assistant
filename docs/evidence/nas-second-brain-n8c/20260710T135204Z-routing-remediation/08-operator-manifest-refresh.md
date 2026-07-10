# Operator manifest refresh — post routing-remediation deploy

The routing remediation expands **published client workflows from 7 to 15**. The persisted vault manifest remains stale until manually refreshed.

**Policy:** stage → review → promote. No auto-promote on deploy.

## Preconditions

- Deploy completed; `runtime_commit` matches remediation SHA.
- `pa_tool_surface_freshness_check` reports live surface current (or documents expected staleness).
- Auto flags remain off:
  - `HB_MCP_MANIFEST_AUTO_STAGE_ON_DRIFT` unset or `0`
  - `HB_MCP_MANIFEST_FIRST_INSTALL_AUTOPROMOTE` unset or `0`

## Step 1 — Freshness check

Via MCP (gateway or direct):

```text
pa_tool_surface_freshness_check
pa_tool_manifest_freshness_check
pa_tool_manifest_review_plan
```

Expect `review_required=true` when persisted manifest is schema 0 or missing 15-workflow projection.

## Step 2 — Stage refresh proposal

```text
pa_tool_manifest_refresh_stage
```

Capture `refresh_proposal_id` from the receipt. Do **not** promote yet.

## Step 3 — Review plan

```text
pa_tool_manifest_review_plan
```

Operator reviews staged diff in vault path under `99 System/Manifests` (bounded write). Confirm:

- `client_projection_schema_version = 1`
- `published_workflow_count = 15`
- Workflow recipes include new categories: `vault_read`, `preference`, `open_loop`, `staging`, `promotion`, `surface_audit`, `manifest_review_plan`

## Step 4 — Promote (server-minted approval required)

```text
pa_artifact_promotion_validate  # if promotion bundle path applies to manifest refresh
pa_tool_manifest_refresh_promote(refresh_proposal_id=..., operator_approval_id=...)
```

Use only the **server-minted** `operator_approval_id` from validation — never forge.

## Step 5 — Verify

```text
pa_tool_manifest_get
pa_tool_manifest_freshness_check
```

Expect active manifest schema 1, semantic checksum aligned with live surface, `staleness_state=current`.

## Rollback

If promoted manifest is wrong: restore prior manifest revision from vault backup / DB row history per N8C-23 runbook; do not delete receipts.