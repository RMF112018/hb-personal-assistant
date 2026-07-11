# RT-01 clean-context rebuild (PR-21/22/23)

**Date:** 2026-07-11  
**Disposition:** `DEPLOYED_AND_VALIDATED` — Tier B image live on NAS (2026-07-11)

## A. Land commit

```text
deploy_sha=542307fc6fc87b7a5713b8917e861a576a03c96c
previous_deploy_sha=931f69f04c697c4082f65fbf90ab2b6ae6c81af9
attestation_tier_target=CODE_VERIFIED_CLEAN_CONTEXT (Tier B)
```

## B. Local build (git archive)

| Field | Value |
|-------|-------|
| Build script | `scripts/build-nas-image.sh` |
| Context method | `git archive HEAD` (clean tree) |
| Platform | `linux/amd64` |
| Image tag | `hb-personal-assistant:nas` |
| Image digest | `sha256:2af0fd38265a8f592afcb9f08d0b4cf0083a3add1d1f051544bd95104ff0009b` |
| Tarball | `/tmp/hb-nas-542307fc.tar.gz` |
| Tarball bytes | 105791674 |
| Tarball SHA-256 | `f39e44dee8d75d8bfd3e5a93874f2e6ff501345e3a7b77068a26eb56ddbed014` |
| Forbidden-path scan | pass (`! -e /app/.claude`, `! -e /app/local_audit_outputs`) |
| `HB_BUILD_COMMIT_VERIFIED` | `0` (Tier B — no registry signing) |

Compared to Tier A dirty build (`931f69f0`): tarball **105 MB** vs **193 MB** (~20,809 junk paths eliminated).

## C. Runtime identity expectation (post-deploy)

| Signal | Expected |
|--------|----------|
| `runtime_commit` | `542307fc6fc87b7a5713b8917e861a576a03c96c` |
| `runtime_identity_kind` | `exact_unverified_stamp` |
| `runtime_identity_verified` | `false` |
| `runtime_image_digest` | `sha256:2af0fd38265a8f592afcb9f08d0b4cf0083a3add1d1f051544bd95104ff0009b` (compose-injected) |
| `/app/.claude` | absent |
| Live required corpus | 47/47 pass |

`exact_verified_commit` **must not** appear until Tier C (registry + cosign).

## D. NAS staging artifacts

Transferred to `hb-nas:/tmp/` (2026-07-11):

| Artifact | Path |
|----------|------|
| Image tarball | `/tmp/hb-nas-542307fc.tar.gz` |
| Build manifest | `/tmp/hb-nas-542307fc.build-manifest.json` |
| Deploy | `/tmp/01-deploy-pr15.sh` |
| Manifest refresh | `/tmp/02-manifest-refresh-pr15.sh` |
| Verify-only | `/tmp/03-manifest-verify-pr15.sh` |
| Live corpus | `/tmp/04-live-50-prompt-corpus.sh` |

NAS tarball size verified: **105791674** bytes (matches local SHA-256).

## E. Operator sequence (complete)

```bash
ssh -t hb-nas 'sudo sh /tmp/01-deploy-pr15.sh' | tee ~/deploy-rt01.txt
ssh -t hb-nas 'sudo sh /tmp/02-manifest-refresh-pr15.sh' | tee ~/manifest-refresh-rt01.txt
ssh -t hb-nas 'sudo sh /tmp/04-live-50-prompt-corpus.sh' | tee ~/live-corpus-rt01.txt
```

All pass criteria met. Detail: `11-rt01-operator-deploy-results.md`