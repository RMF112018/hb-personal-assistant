# Manifest Refresh Closeout — PR #293 routing remediation

**Date:** 2026-07-10  
**Operator:** Bobby (interactive `sudo` over `ssh -t hb-nas`)  
**Disposition:** `PROMOTED` — post-promote script verification failed on wrong workflow count; promote itself succeeded.

## A. Pre-promote freshness (expected drift)

```text
staleness_state=stale
review_required=true
tool_manifest_missing_tools=[
  pa_prompt_route, pa_prompt_route_explain, pa_tool_family_get,
  pa_tool_surface_freshness_check, pa_workflow_recipe_get
]
manifest_version=3
checksum=e199d588ce098cdd37a6b673
live_tool_count=145
```

Classification / family / semantic drift on assistant workflow and artifact tools was expected — live surface had moved ahead of persisted manifest.

## B. Stage

```text
refresh_proposal_id=c6f6196210167dee42624134
operator_approval_id=b9a7e5fb15c8489426dcfe93
status=staged
request_id=32259730d92d428da85583f5c3b38c14
```

## C. Promote

```text
status=promoted
manifest_id=1f07b061308fddfa8f6923b4
md_path=99 System/Manifests/client-tool-operating-manifest.md
json_path=99 System/Manifests/client-tool-operating-manifest.json
checksum=5ac5677779777f6fa7e62b05
full_semantic_checksum=sha256:026464e9472b69de869c9dc9aa4cc41559f70bc99a45692de94e74249ad613bf
client_projection_checksum=sha256:f4f84d7fc4a8b1a4f9db89d28578f2dbd88e07d5477de5574836ed363a287256
client_projection_chars=50873
idempotent_reuse=false
request_id=60866b89efd14b638a543a29d9f148d9
```

## D. Post-promote verification (partial — script bug)

Operator ran `14-manifest-refresh.sh`. Step 4 printed:

```text
manifest_status active persisted True
manifest_schema_version 1
workflow_count 14 published_recipes 14
staleness fresh stale False review_required False
```

Then failed:

```text
AssertionError: 14
```

**Root cause:** script had `EXPECT_PUBLISHED=15`; R6 publishes **14** client workflows (`publish_to_client_manifest=True` in `workflow_recipe_manifest.py`). Promote and freshness checks were already green.

**Remediation:** `14-manifest-refresh.sh` corrected to `EXPECT_PUBLISHED=14` and asserts `workflow_count == len(WORKFLOW_RECIPES) == 14`. Use `15-manifest-verify-only.sh` to finish steps 4–5 without re-promoting.

## E. Operator follow-up (one command)

```bash
scp docs/evidence/nas-second-brain-n8c/20260710T135204Z-routing-remediation/15-manifest-verify-only.sh hb-nas:/tmp/
ssh -t hb-nas 'sudo sh /tmp/hb-manifest-verify-only.sh' | tee ~/manifest-verify-only.txt
```

Expect step 5: `document_session` (or equivalent workflow) **not** blocked by `surface_stale`.

## F. Verify-only rerun (2026-07-10)

```text
manifest_status active persisted True
manifest_schema_version 1
workflow_count 14 published_recipes 14
tool_manifest_stale False review_required False
manifest refresh verified

pa_prompt_route document_session → executable False blocked surface_stale
```

Name-level manifest is fresh; write-route gate still blocked. See `16-surface-stale-root-cause.md`.

## G. Code fix (repo)

`build_tool_entry()` classification parity with promoted manifest entries (`classify_tool`). Requires NAS redeploy + manifest re-promote (runtime commit baseline).

## H. Final disposition

| Gate | Status |
| --- | --- |
| Stage | PASS |
| Promote | PASS |
| Persisted manifest schema 1 | PASS |
| `pa_tool_manifest_freshness_check` | PASS |
| Script workflow-count assert | FAIL → fixed (`EXPECT_PUBLISHED=14`) |
| `pa_tool_surface_freshness_check` | FAIL (classification parity bug) |
| `document_session` routing | FAIL (`surface_stale`) — fixed pending deploy |

`MANIFEST_PROMOTED` on R1/R2; `WRITE_ROUTES_UNBLOCKED` after freshness-fix deploy (`f565b19b`) + manifest R3 — see `18-freshness-fix-deploy-closeout.md`.