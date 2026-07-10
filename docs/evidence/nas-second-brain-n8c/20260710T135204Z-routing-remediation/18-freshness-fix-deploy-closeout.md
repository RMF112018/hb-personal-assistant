# Freshness-fix deploy + manifest R3 closeout

**Date:** 2026-07-10  
**Operator:** Bobby  
**Disposition:** `DEPLOYED_AND_VALIDATED` — write routes unblocked

## A. Deploy identity

```text
deploy_sha=f565b19b1525fbeef75077c53be2b3bb0520c274
previous_deployed_sha=f53cba1c7b4bcba0c5d7bb82aa63694c3041f0e3
image_id=sha256:87bc1615f215799ea48032c352d00835193a99d8c19770a96d609b2d949be7ed
tarball=/tmp/hb-nas-f565b19b.tar.gz
compose_backup=/volume2/personal-assistant/deploy/nas/mcp/compose-mcp.yaml.bak-20260710T201909Z
runtime_commit_live=f565b19b1525fbeef75077c53be2b3bb0520c274 (exact_commit)
schema_head=119 (unchanged)
```

## B. Post-deploy freshness (pre–manifest R3)

Deploy step 7 smoke (expected stale until manifest re-promote):

```text
family_changed=0
class_changed=0
stale=True
warnings=profile_context_changed:unknown->remote_cloudflare, deployment_runtime_commit_mismatch
```

Classification parity fix verified live; profile + runtime commit baseline still needed manifest R3.

## C. Manifest R3

```text
refresh_proposal_id=32b1a5d3ac0e209f8ff64e2e
operator_approval_id=b1f6354c0a02b3e7e6493fe7
manifest_id=c231773ac1d1be2815ac6fa8
manifest_version=6 (promoted row; pre-stage header was v5)
legacy_checksum=5ac5677779777f6fa7e62b05 (unchanged — tool triad stable)
full_semantic_checksum=sha256:026464e9472b69de869c9dc9aa4cc41559f70bc99a45692de94e74249ad613bf
client_projection_checksum=sha256:2c96d12d38e8efc6cc04e7cc4b8dd1b74f09e4041319223b1a2b39c641220179 (changed — profile/exposure stamped)
```

## D. Post–manifest R3 verification (14-manifest-refresh.sh)

| Check | Result |
| --- | --- |
| `manifest_status active` / `persisted True` | PASS |
| `manifest_schema_version 1` | PASS |
| `workflow_count 14` | PASS |
| `pa_tool_manifest_freshness_check` stale False | PASS |
| `pa_prompt_route` document_session | **PASS** — `executable True`, `blocked None` |

## E. Root-cause fixes landed (f565b19b)

1. `get_active()` hydrates `tool_family` from `manifest_payload_json`
2. Stage/promote stamps `surface_profile` + `gate_state_snapshot`
3. `build_tool_entry()` uses `classify_tool()` for classification parity

## F. Final disposition

`MANIFEST_REFRESHED` + `WRITE_ROUTES_UNBLOCKED` — PR #293 routing remediation stack complete through operator manifest closeout.

**Residual:** None blocking `document_session` or surface-stale write gate.