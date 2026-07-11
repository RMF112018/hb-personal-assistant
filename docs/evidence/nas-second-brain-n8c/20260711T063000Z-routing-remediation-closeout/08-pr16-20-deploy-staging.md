# PR-16..PR-20 deploy staging (2026-07-11)

**Disposition:** `STAGED_ON_NAS` — image + scripts transferred; operator `sudo` required for load/restart.

## Identity

| Field | Value |
|-------|-------|
| `deploy_sha` | `931f69f04c697c4082f65fbf90ab2b6ae6c81af9` |
| `short_sha` | `931f69f0` |
| `image_id` | `sha256:0649607d05586efe4170253573b635e11b68c4c6adeff8e895cc2a46a5c5b6fd` |
| `tarball` | `/tmp/hb-nas-931f69f0.tar.gz` |
| `tarball_bytes` | 193164199 |
| `tarball_sha256` | `566be8bcea3d3ffecbc0b15f729cd054d3990cc44b8dc2f58d34cf298d675ced` |
| `schema_policy` | code-only; `EXPECT_HEAD=119` |

## Local gates (pre-staging)

- `scripts/test-prompt-routing-audit.sh` — PASS
- `scripts/verify-routing-remediation-claims.sh` — `LOCAL_CLAIMS_VERIFIED`

## NAS staging (non-sudo)

Transferred 2026-07-11 to `hb-nas:/tmp/`:

- `hb-nas-931f69f0.tar.gz` (SHA verified on NAS)
- `01-deploy-pr15.sh` … `04-live-50-prompt-corpus.sh` (DEPLOY_SHA updated)

## Blocker

`sudo -n` denied for `bfetting` — deploy load/restart requires interactive sudo on NAS.

## Operator sequence (one session)

```bash
ssh -t hb-nas 'sudo sh /tmp/01-deploy-pr15.sh' | tee ~/deploy-pr16-20.txt
ssh -t hb-nas 'sudo sh /tmp/02-manifest-refresh-pr15.sh' | tee ~/manifest-refresh-pr16-20.txt
ssh -t hb-nas 'sudo sh /tmp/03-manifest-verify-pr15.sh' | tee ~/manifest-verify-pr16-20.txt
ssh -t hb-nas 'sudo sh /tmp/04-live-50-prompt-corpus.sh' | tee ~/live-corpus-pr16-20.txt
```

Pass criteria:

- Runtime commit `931f69f04c697c4082f65fbf90ab2b6ae6c81af9`
- Manifest `workflow_count 15`, `tool_manifest_stale False`
- Live corpus **47 required** rows pass (`fail_count 0`)