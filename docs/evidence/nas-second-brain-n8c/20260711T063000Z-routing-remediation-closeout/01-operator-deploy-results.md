# PR-15 operator deploy results (2026-07-11)

**Runtime:** `01b9b00bb2e79a6523397073152b56fe14c01527`  
**Disposition:** `DEPLOYED` — manifest refresh blocked; live corpus **PASS**

## Gate summary

| Step | Script | Result | Notes |
|------|--------|--------|-------|
| Deploy | `01-deploy-pr15.sh` | **PARTIAL** | Steps 0–6 PASS; step 7 freshness assert failed (expected pre-refresh) |
| Manifest refresh (r1) | `02-manifest-refresh-pr15.sh` | **FAIL** | `schema_index_not_frozen` (script lacked registration bootstrap) |
| Manifest refresh (r2) | `02-manifest-refresh-pr15.sh` | **PARTIAL** | Stage + promote PASS; 15 workflows; step 4b false stale (broker exec) |
| Verify-only (r2) | `03-manifest-verify-pr15.sh` | **PARTIAL** | Manifest verified; step 4b `semantic_surface_checksum_mismatch` |
| Live corpus | `04-live-50-prompt-corpus.sh` | **PASS** | 42/42 required rows; spot checks rows 1, 25, 36 OK |

## Manifest R4 (r2) — promoted

```text
refresh_proposal_id=ddf63a4388dd5b1423856926
operator_approval_id=c0fd00b71c1f431224ff11e9
manifest_id=f70f0a8711d053f32c910aa8
workflow_count=15 published_recipes=15
tool_manifest_stale=False
full_semantic_checksum=sha256:346a50a511b2d59dc1cff30575c292cc98a7a9910c210d46d656a81705b7480e
```

## Root cause — step 4b false stale (r2)

Same broker-only `docker exec` issue: stage/promote bootstrapped `register_nas_mcp_tools` (frozen schema →
checksum X), but step 4b freshness ran without registration (empty schema → checksum Y ≠ X).

**Not a real drift** — manifest is fresh; script assertion was wrong context.

## Root cause — manifest stage failure (r1)

`pa_tool_manifest_refresh_stage` (F-008) requires a **frozen FastMCP schema index** captured by
`register_nas_mcp_tools`. Operator scripts used `docker exec … NasMcpBroker().dispatch()` in a **fresh
Python process** without registration, so `_LIVE_TOOL_SCHEMA_INDEX` was empty.

The running MCP server process *does* have a frozen index; broker-only `docker exec` paths do not share it.

## Root cause — freshness / verify failures (expected until refresh)

Pre-refresh surface reported:

- `class_changed_tools`: `hb_assistant_tool_query` (gateway proxy now classified write)
- `deployment_runtime_commit_mismatch` (persisted manifest still on prior runtime)
- `semantic_surface_checksum_mismatch`
- `workflow_count` 14 vs `WORKFLOW_RECIPES` 15 (`mixed_private_retrieval` published in PR-15)

All clear after successful stage → promote.

## Remediation applied (repo)

1. `02-manifest-refresh-pr15.sh` — bootstrap `register_nas_mcp_tools` before stage/promote dispatch.
2. `01-deploy-pr15.sh` — step 7 no longer hard-fails on pre-refresh staleness.
3. `ensure_schema_index_frozen()` in `tool_registration.py` — auto-freeze on refresh stage (next image).

## Operator follow-up (one sequence)

NAS has no working `scp` — use `ssh … 'cat > /tmp/…'` (same pattern as v117 deploy).

```bash
# From repo root on Mac
ssh hb-nas 'cat > /tmp/02-manifest-refresh-pr15.sh' \
  < docs/evidence/nas-second-brain-n8c/20260711T063000Z-routing-remediation-closeout/02-manifest-refresh-pr15.sh
ssh hb-nas 'cat > /tmp/03-manifest-verify-pr15.sh' \
  < docs/evidence/nas-second-brain-n8c/20260711T063000Z-routing-remediation-closeout/03-manifest-verify-pr15.sh

ssh hb-nas 'cat > /tmp/03-manifest-verify-pr15.sh' \
  < docs/evidence/nas-second-brain-n8c/20260711T063000Z-routing-remediation-closeout/03-manifest-verify-pr15.sh

ssh -t hb-nas 'sudo sh /tmp/03-manifest-verify-pr15.sh' | tee ~/manifest-verify-pr15-r3.txt
```

r3 result: steps 4 + 4b PASS; step 5 false `surface_stale` (broker-exec bootstrap gap on step 5 only).

## r4 verify-only — final (2026-07-11)

```text
manifest_status active persisted True
workflow_count 15 published_recipes 15
tool_manifest_stale False

pa_tool_surface_freshness_check:
  stale=false staleness_state=current warnings=[]

pa_prompt_route document_session:
  executable=True blocked=None
```

**Disposition:** `DEPLOYED_AND_VALIDATED` — PR-15 operator closeout complete.

## Residual (non-blocking)

Repo-side hardening (not yet on NAS image `01b9b00b`): `ensure_schema_index_frozen()` in
`live_freshness` + manifest refresh stage so operator `docker exec` paths do not require manual
`register_nas_mcp_tools` bootstrap. Land on next NAS image build.