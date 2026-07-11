# RT-01 operator deploy results (2026-07-11)

**Disposition:** `DEPLOYED_AND_VALIDATED` — Tier B clean-context image live on NAS

## Identity

| Field | Value |
|-------|-------|
| `deploy_sha` | `542307fc6fc87b7a5713b8917e861a576a03c96c` |
| `previous_runtime` | `931f69f04c697c4082f65fbf90ab2b6ae6c81af9` (Tier A dirty build) |
| `loaded_image_id` | `sha256:62c2e553fe114a686cbb28f1fbb2254a1fac93b6d66098d2033242dc5b97adb3` |
| `runtime_image_digest` | `sha256:2af0fd38265a8f592afcb9f08d0b4cf0083a3add1d1f051544bd95104ff0009b` |
| `runtime_identity_kind` | `exact_unverified_stamp` |
| `runtime_identity_verified` | `false` |
| `image_attestation_tier` | `CODE_VERIFIED_CLEAN_CONTEXT` (Tier B) |
| `runtime_build_timestamp` | `20260711T084339Z` |
| `manifest_version` | 8 |
| `published_workflows` | 15 |
| `compose_backup` | `compose-mcp.yaml.bak-20260711T084529Z` |

## Schema lineage

| DB | Head | Notes |
|----|------|-------|
| Live / RO snapshot (deploy step 3) | **119** | Code-only deploy policy (`EXPECT_HEAD=119`) |
| RW workspace (host, step 3b) | **121** | `LATEST_SCHEMA_VERSION` |

## Gate results

| Step | Result |
|------|--------|
| `01-deploy-pr15.sh` | PASS — digest injected, snapshot refreshed (4.39 GB), MCP restarted, Tier B identity + forbidden-path scan |
| Pre-refresh freshness | `stale True` (`deployment_runtime_commit_mismatch` — expected) |
| `02-manifest-refresh-pr15.sh` | PASS — staged `c5b89e35…`, promoted `88b5644d…`, `workflow_count 15`, surface `stale false` |
| `04-live-50-prompt-corpus.sh` | PASS — **47/47 required**, `fail_count 0`, Tier B identity re-verified |

## Tier B attestation proof

| Check | Result |
|-------|--------|
| Clean build context (`git archive`) | yes (baked manifest `context_clean: true`) |
| `/app/.claude` absent | yes (deploy + corpus forbidden-path scan) |
| `HB_BUILD_IMAGE_DIGEST` at runtime | yes (compose-injected) |
| `HB_BUILD_COMMIT_VERIFIED` | `0` (policy-correct for Tier B) |
| `exact_verified_commit` claimed | **no** (correct — deferred to Tier C) |
| Tarball size | 105791674 bytes (vs 193164199 Tier A) |

## HIGH-row spot checks (live)

| Row | Workflow | Next tool | Executable |
|-----|----------|-----------|------------|
| 01 | `read_only_surface_audit` | `hb_mcp_status` | true |
| 25 | `canonical_decision_retrieval` | `assistant_get_decision` | true |
| 36 | `mixed_private_retrieval` | `assistant_source_file_search` | true |

## Operator transcripts

Local paths (operator machine):

- `~/deploy-rt01.txt`
- `~/manifest-refresh-rt01.txt`
- `~/live-corpus-rt01.txt`

## Residual notes

- Tier C (`RT-01_CLOSED_VERIFIED`) remains deferred — registry digest + cosign attestation chain not in scope.
- `03-manifest-verify-pr15.sh` not re-run; step 4b in manifest refresh already verified surface freshness.
- Full 50-case informational replay not captured in transcript excerpt; **47 required** gate is the completion standard.