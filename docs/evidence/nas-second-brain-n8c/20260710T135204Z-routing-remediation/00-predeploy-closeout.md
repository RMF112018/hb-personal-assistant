# Pre-deploy closeout — PR #293 routing remediation (R1–R6)

**Date:** 2026-07-10  
**Bundle:** `20260710T135204Z-routing-remediation`  
**Disposition:** `DEPLOYED_AND_VALIDATED` — see `12-deploy-closeout.md`

## Scope

Remediate independent audit `FAIL_REMEDIATION_REQUIRED` findings for prompt routing accuracy and contract gaps while preserving confirmed safety posture (fail-closed writes, no ID fabrication).

| Phase | Focus | Status |
| --- | --- | --- |
| R1 | Modality + clause negation | code complete |
| R2 | Schema-aware argument extraction | code complete |
| R3 | Executability evaluator + route schema v2 fields | code complete |
| R4 | Workflow alignment + 40-case audit harness | code complete |
| R5 | Failure envelope normalization | code complete |
| R6 | Client manifest publication (7 → 15 workflows) | code complete |

## Identity

```text
currently_deployed_runtime_sha=14dfc3a0e007475543e19f1d8efd999b23f3e28b
local_git_head=dc523eaf34a1f959db2cdb1a45a15ac3327b0941
deploy_target_sha=TBD — commit remediation stack first, then rebuild image from that SHA
schema_head=119 (no new migration in this stack — code-only deploy)
published_client_workflows=15 (was 7 on deployed image)
```

**Blocker before build:** remediation changes are **uncommitted** in the local worktree. Operator must land a single commit (or PR merge) containing R1–R6, then set `DEPLOY_SHA` in `06-deploy-script.sh` to the landed SHA.

## Offline validation (Mac worktree)

| Gate | Result | Artifact |
| --- | --- | --- |
| Audit regression matrix (offline `route_prompt`) | **40/40 PASS** | `01-audit-regression-matrix-offline.json` |
| Audit regression matrix (broker temp DB) | **40/40 PASS** | `02-audit-regression-matrix-broker.json` |
| Route proof matrix | **20/20 PASS** | `03-route-proof-matrix-run.txt` |
| Prompt preflight smoke | **PASS** | `04-smoke-prompt-preflight.txt` |
| Routing + envelope + manifest guards | **PASS** | `05-pytest-routing-guards.txt` |

## Safety posture (unchanged)

- No unauthorized writes, approval bypass, ID fabrication, or false executable writes confirmed in offline matrix.
- Manifest auto-stage / auto-promote flags remain **off** (`HB_MCP_MANIFEST_AUTO_STAGE_ON_DRIFT`, `HB_MCP_MANIFEST_FIRST_INSTALL_AUTOPROMOTE`).
- Post-deploy manifest refresh is **manual** (stage → review → promote with server-minted approval).

## Operator sequence (authorized)

1. **Commit + push** remediation stack; record landed SHA.
2. **Build + transfer** image per `07-build-and-transfer.md`.
3. **Deploy** on NAS via `06-deploy-script.sh` (code-only; schema 119 unchanged).
4. **Live probe** 40-prompt matrix via `09-live-40-prompt-probe.sh`.
5. **Manifest refresh** per `08-operator-manifest-refresh.md` (manual; schema-1 payload).

## Rollback anchors (from prior deploy)

- Image: `hb-personal-assistant:prev`
- DB: latest `hb-personal-assistant.pre-v119.*.sqlite` backup (schema unchanged this deploy)
- Compose: latest `compose-mcp.yaml.bak-*`

## Residual / known

- `test_n8c22_invariants_preserved` may fail locally when assistant_output_* aliases are registered (environment parity); not a routing-regression gate.
- `read_only_surface_audit` / `status_check` cases show `gateway_denied` in broker temp-db mode because `hb_mcp_status` is not gateway-allowlisted — expected; live connector uses direct tool exposure or catalog path.