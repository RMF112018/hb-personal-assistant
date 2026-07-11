# PR-16..PR-20 operator deploy results (2026-07-11)

**Disposition:** `DEPLOYED_AND_VALIDATED`

## Identity

| Field | Value |
|-------|-------|
| `deploy_sha` | `931f69f04c697c4082f65fbf90ab2b6ae6c81af9` |
| `previous_runtime` | `01b9b00bb2e79a6523397073152b56fe14c01527` |
| `loaded_image_id` | `sha256:19f28e1deaff49fc7cf5c95de4a2ed94e0075c7aff56aadf661daf0116a3d36d` |
| `runtime_identity_kind` (reported) | `exact_verified_commit` (overstated — see RT-01) |
| `image_attestation_tier` | `CODE_VERIFIED_IMAGE_UNATTESTED` |
| `runtime_build_timestamp` | `20260711T072424Z` |
| `manifest_version` | 7 |
| `published_workflows` | 15 |

## Schema lineage

| DB | Head | Notes |
|----|------|-------|
| Live / RO snapshot (deploy step 3) | **119** | Code-only deploy policy (`EXPECT_HEAD=119`) |
| RW workspace (host, step 3b) | **121** | `LATEST_SCHEMA_VERSION` |
| Container verify step 3c `RO_snapshot_head` | `(absent)` | `HB_ASSISTANT_DB` not exposed in exec env — informational only; deploy host check authoritative |

## Gate results

| Step | Result |
|------|--------|
| `01-deploy-pr15.sh` | PASS — snapshot refreshed (4.39 GB), MCP restarted, runtime commit verified |
| Pre-refresh freshness | `stale True` (expected) |
| `02-manifest-refresh-pr15.sh` | PASS — staged `f677ef30…`, promoted `b0f45562…`, `workflow_count 15`, surface `stale false` |
| `03-manifest-verify-pr15.sh` | PASS — manifest + surface freshness + document_session spot-check |
| `04-live-50-prompt-corpus.sh` | PASS — **47/47 required**, `fail_count 0` |

## HIGH-row spot checks (live)

| Row | Workflow | Next tool | Executable |
|-----|----------|-----------|------------|
| 01 | `read_only_surface_audit` | `hb_mcp_status` | true |
| 25 | `canonical_decision_retrieval` | `assistant_get_decision` | true |
| 36 | `mixed_private_retrieval` | `assistant_source_file_search` | true |

## RT-03..RT-06 rows (live required tier)

| Row | Prompt (abbrev) | Pass |
|-----|-----------------|------|
| 06 | Do not stage; only summarize | yes |
| 11 | Which files are relevant | yes (`query=relevant files`) |
| 22 | What would happen if I promoted | yes (`plan_canonical_promotion`) |
| 29 | Open loops relate to NAS deployment | yes |
| 35 | Find references to ID in notes | yes |
| 40 | Create a proposal; do not promote | yes |

## Operator transcripts

Local paths (operator machine):

- `~/deploy-pr16-20.txt`
- `~/manifest-refresh-pr16-20.txt`
- `~/manifest-verify-pr16-20.txt`
- `~/live-corpus-pr16-20.txt`

## Residual notes

- **RT-01:** Image built from dirty checkout (`~20k` extra files, mostly `.claude/worktrees/`). `HB_BUILD_COMMIT_VERIFIED=1` overstated identity — policy-correct tier is `CODE_VERIFIED_IMAGE_UNATTESTED`. See `RT-01-image-attestation-tiers.md`; superseded by clean rebuild (PR-23).
- First deploy attempt failed at step 3b (container mount bug); fixed in `fc4bf0f1`, re-run succeeded.
- Full 50-case informational replay not captured in transcript excerpt; **47 required** gate is the completion standard.
- `accepted_partial` rows (3, 4, 19) remain intentional explain/advisory debt.