# RT-01 — Image attestation tiers

**Date:** 2026-07-11  
**Scope:** NAS `hb-personal-assistant:nas` image qualification (independent of routing corpus pass)

## Disposition key

| Tier | Label | When to use |
|------|-------|-------------|
| **A** | `CODE_VERIFIED_IMAGE_UNATTESTED` | Git SHA stamped + routing gates pass; image built from dirty context and/or no attestation chain |
| **B** | `CODE_VERIFIED_CLEAN_CONTEXT` | Tier A + `git archive` clean build + forbidden-path scan pass + digest recorded at deploy |
| **C** | `RT-01_CLOSED_VERIFIED` | Tier B + registry digest + immutable ref + OCI labels + signed provenance chain (deferred) |

`RT-01_CLOSED_VERIFIED` **must not** be claimed for tarball-only `docker load` deploys without registry signing.

## What each tier proves

| Signal | Tier A (`931f69f0`) | Tier B (clean rebuild) | Tier C (future) |
|--------|---------------------|------------------------|-----------------|
| `HB_RUNTIME_COMMIT` stamp | yes | yes | yes |
| Live/offline routing corpus | 47/47 | 47/47 | 47/47 |
| Clean build context (`git archive`) | no | yes | yes |
| No `/app/.claude` in image | no (~20k junk files) | yes (scan) | yes |
| `HB_BUILD_IMAGE_DIGEST` at runtime | optional | yes (compose inject) | yes (registry) |
| `runtime_identity_verified` | **false** | **false** | true |
| `runtime_identity_kind` | `exact_unverified_stamp` | `exact_unverified_stamp` | `exact_verified_commit` |
| Registry / cosign attestation | no | no | yes |

## Runtime identity policy (F-002 + RT-01)

`exact_verified_commit` requires **all**:

1. Valid SHA in `HB_RUNTIME_COMMIT` or `HB_BUILD_SHA`
2. `HB_BUILD_COMMIT_VERIFIED=1`
3. `HB_BUILD_IMAGE_DIGEST` matching `sha256:<64-hex>`
4. `/app/.hb-build-manifest.json` with `"context_clean": true`

Current operator pipeline sets `HB_BUILD_COMMIT_VERIFIED=0` (Tier B). Tier C may set verified=1 only after registry signing lands.

## Build hygiene finding (`931f69f0`)

Dirty `docker build .` from primary checkout baked **20,809** non-application paths, primarily:

- `.claude/worktrees/…` (20,733)
- `local_audit_outputs/` (60)
- other dev trees

Remediation: [`scripts/build-nas-image.sh`](../../../../scripts/build-nas-image.sh) — mandatory for production NAS images.