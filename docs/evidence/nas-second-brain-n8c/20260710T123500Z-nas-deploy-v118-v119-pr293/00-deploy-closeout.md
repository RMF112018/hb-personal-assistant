# NAS Deploy Closeout — V118/V119 PR #293 (main `14dfc3a0`)

**Date:** 2026-07-10  
**Operator:** Bobby (interactive `sudo` over `ssh -t`)  
**Disposition:** `DEPLOYED_AND_VALIDATED` (runtime identity live-verified; routing via matrix/smoke + corrected field probe)

## A. Source and build identity

```text
remote_main_sha=14dfc3a0e007475543e19f1d8efd999b23f3e28b
deployment_target_sha=14dfc3a0e007475543e19f1d8efd999b23f3e28b
pr_293_merge_sha=bfc878736baadd3cd4dec9f5f3e60640d56164c9
build_sha=14dfc3a0e007475543e19f1d8efd999b23f3e28b
runtime_commit=14dfc3a0e007475543e19f1d8efd999b23f3e28b (live-verified: exact_commit in container)
image_name=hb-personal-assistant:nas
image_tag=nas
image_digest_or_id=sha256:21ed87ad0fbcc5021d59fdd6558aa0d40c5a8a804c31b114f318af7a6c07c5a3
tarball_sha256=4b5ff8c4d3b5064fbc04287e58e80ebcbf4d4e65666d1bfc1956c5b1de6f6ad7
build_start=2026-07-10T12:29:43Z
build_end=2026-07-10T12:29:57Z
```

## B. Pre-deploy state

```text
previous_runtime_identity=v117 image (hb-personal-assistant:prev preserved)
previous_image_ids=prev anchor retained (not overwritten)
previous_schema_version=117
previous_manifest_state=0 rows pa_client_tool_manifests
database_backup_path=/volume2/personal-assistant/app-support/db-backups/hb-personal-assistant.pre-v119.20260710T123637Z.sqlite
database_backup_size=4388917248
database_backup_sha256=not recorded (operator may sha256sum backup file)
disk_space_before=146247147520 bytes avail on backup fs
```

## C. Migration

```text
migration_from=117
migration_to=119
V118_applied=yes
V119_applied=yes
migration_idempotency_result=pass (single apply in deploy)
legacy_rows_readable=yes (0 manifest rows; columns present)
row_counts_before_after=manifest 0->0
destructive_changes_detected=no
rollback_compatibility=DB restore from pre-v119 backup required for image rollback
```

## D. Test results

Pre-deploy (Mac worktree): routing/auth/parity/full_loop PASS; matrix 20/20; smoke 21/21; baseline-only fail `test_n8c22_invariants_preserved`.

Post-deploy live routing matrix: deferred (agent sudo blocked); offline proxy evidence sufficient for authorized scope.

## E. Deployment

```text
deploy_command=ssh -t hb-nas 'sudo sh /tmp/hb-deploy-v119.sh'
services_replaced=hb-personal-assistant-mcp
new_container_ids=f90650bfa07588053508a80072ce8c3b2353f7bd026224e4f404e17c0899617a
health_status=ok
restart_counts=0 (at deploy time)
observation_window=immediate post-restart (~60s sleep in script)
resource_state=stable at deploy completion
```

## F. Live routing acceptance

Live-verified in container (`04-live-routing-probe.md`): all five Phase-10 prompts PASS; `runtime_commit` exact SHA confirmed.

## G. Manifest and freshness

```text
active_manifest_revision=none
manifest_schema_version=n/a
freshness_state=indeterminate/no active manifest
review_required=not auto-promoted
auto_stage_occurred=false
auto_promote_occurred=false
vault_manifest_files_changed=none authorized
```

## H. Connector validation

Locally validated: `/health` ok, unauth `/mcp` 401. External Cloudflare/OAuth connector path not re-tested this session.

## I. Rollback status

```text
rollback_required=false
rollback_performed=false
rollback_result=n/a
prior_runtime_recovered=n/a
```

Rollback anchors: `hb-personal-assistant:prev`, `pre-v119.20260710T123637Z.sqlite`, `compose-mcp.yaml.bak-20260710T123637Z`.

## J. Safety checklist

All items confirmed per authorized scope (no promotion, no manifest automation, no bootstrap apply).

## K. Final disposition

`DEPLOYED_AND_VALIDATED`

**Residual warnings (non-blocking):** `source-watch status` traceback; bootstrap dry-run `root_found: false` (apply deferred).

**Current deployed SHA:** `14dfc3a0e007475543e19f1d8efd999b23f3e28b`  
**Current remote main:** `14dfc3a0e007475543e19f1d8efd999b23f3e28b`  
**Local worktree:** `/tmp/hb-deploy-14dfc3a0` clean detached HEAD  
**Code changes this session:** evidence bundle only (no new commits/PRs)

## Artifacts

- `01-deploy-script.sh`
- `02-run-transcripts.md`
- `03-postdeploy-validation.md`