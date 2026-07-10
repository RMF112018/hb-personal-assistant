# NAS Deploy Closeout — PR #293 routing remediation (R1–R6)

**Date:** 2026-07-10  
**Operator:** Bobby (interactive `sudo` over `ssh -t`)  
**Disposition:** `DEPLOYED_AND_VALIDATED`

## A. Source and build identity

```text
deploy_sha=f53cba1c7b4bcba0c5d7bb82aa63694c3041f0e3
previous_deployed_sha=14dfc3a0e007475543e19f1d8efd999b23f3e28b
image_name=hb-personal-assistant:nas
image_id=sha256:08b9fb0531ffa95f990ce3296e2f027cfbe1b4a6c44a105cad1260a7b6db0e24
image_platform=linux/amd64
tarball=/tmp/hb-nas-f53cba1c.tar.gz
tarball_sha256_amd64=8b2dd2e478c2bf4e25af34cf6bfd5f420f15841c75d23b6453930ad62e4b6fdb
runtime_commit_live=f53cba1c7b4bcba0c5d7bb82aa63694c3041f0e3 (exact_commit)
container_id=b246085bd52827bc4665bb7754d92698223afe8c2ca191c96624c200bb466537
```

## B. Pre-deploy state

```text
previous_runtime=14dfc3a0 (v119 image)
schema_head=119 (unchanged)
rollback_anchor=hb-personal-assistant:prev (preserved)
compose_backup=/volume2/personal-assistant/deploy/nas/mcp/compose-mcp.yaml.bak-20260710T141255Z
```

## C. Migration

```text
migration_performed=no (code-only deploy)
live_db_head=119
ro_snapshot_bytes=4388986880
ro_snapshot_qc=ok
```

## D. Deploy gates (operator transcript)

| Check | Pass |
| --- | --- |
| Preconditions | yes |
| HB_RUNTIME_COMMIT injected | yes |
| amd64 image loaded | yes |
| Schema head 119 | yes |
| RO snapshot refreshed | yes |
| MCP restarted | yes |
| Health endpoint | yes |
| Runtime commit exact match | yes |
| Routing smoke (3 prompts) | yes |
| Origin auth 401 | yes |

## E. Live routing acceptance

| Probe | Result |
| --- | --- |
| 40-case audit matrix (live broker) | **40/40 PASS** |
| Failure envelope R5 spot-check | PASS |
| Runtime identity | `exact_commit` |

Notable live behaviors (expected):

- `read_only_surface_audit` / `status_check` → `gateway_denied` for `hb_mcp_status` (not gateway-allowlisted).
- `document_session_capture` → `surface_stale` on write route (fail-closed; manifest not yet refreshed).

## F. Manifest and freshness

```text
active_manifest_revision=unchanged at deploy time (manual refresh deferred)
published_workflows_in_code=14
auto_stage_occurred=false
auto_promote_occurred=false
```

**Follow-up:** manual manifest refresh per `08-operator-manifest-refresh.md` — completed in `15-manifest-refresh-closeout.md`.

## G. Rollback

```text
rollback_required=false
rollback_anchors=hb-personal-assistant:prev, compose-mcp.yaml.bak-20260710T141255Z
```

## H. Final disposition

`DEPLOYED_AND_VALIDATED` — audit remediation routing stack live at `f53cba1c`; independent audit routing matrix passes on deployed runtime.

**Residual (non-blocking):** persisted client manifest stale until operator stage/review/promote; `document_session` write route correctly blocked by surface staleness until manifest refresh.