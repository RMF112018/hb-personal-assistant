# Routing audit remediation closeout (PR-15 + PR-16..20)

**Date:** 2026-07-11  
**Disposition:** `DEPLOYED_AND_VALIDATED` — PR-15 closeout + PR-16..20 wave live on NAS

## A. Repository identity

```text
deploy_sha=01b9b00bb2e79a6523397073152b56fe14c01527
github_origin_main=01b9b00bb2e79a6523397073152b56fe14c01527 (verified reachable)
remediation_prs=PR-1..PR-14 landed; PR-15 operator closeout
schema_head=119 (unchanged)
published_workflows=15 (includes mixed_private_retrieval)
```

## B. Local pre-deploy validation

| Gate | Result |
|------|--------|
| `scripts/test-prompt-routing-audit.sh` | PASS (see `05-predeploy-pytest.txt`) |
| `tests/test_prompt_preflight_*.py` + freshness guards | PASS |
| Offline corpus v1 | 50/50 pass |
| Docker build `hb-personal-assistant:nas` | PASS (`06-docker-build.log`) |

Image artifact: `07-image-artifact.txt`  
Tarball SHA-256: `c93ee1caf2fa59328ea3448c7d76a41442fd71c89fc6ae49790e3eb6fda836de`

## C. NAS staging (non-sudo)

Transferred to `hb-nas:/tmp/` on 2026-07-11:

- `hb-nas-01b9b00b.tar.gz` (193131985 bytes)
- `01-deploy-pr15.sh` … `04-live-50-prompt-corpus.sh`

Automated deploy blocked: NAS `sudo` requires interactive password (`sudo -n` denied).

## D. Operator steps remaining

See `00-operator-runbook.md`:

1. `sudo sh /tmp/01-deploy-pr15.sh`
2. `sudo sh /tmp/02-manifest-refresh-pr15.sh`
3. `sudo sh /tmp/03-manifest-verify-pr15.sh` (optional)
4. `sudo sh /tmp/04-live-50-prompt-corpus.sh`

Target: **42/42 required** live corpus pass, **0 HIGH/blocker** regressions; document any `accepted_partial` rows.

## E. Remediation plan status

| Phase | Status |
|-------|--------|
| PR-1..PR-13 routing fixes | Landed on `main` |
| PR-14 versioned corpus | Landed (`01b9b00b`) |
| PR-15 deploy + manifest + live replay | **COMPLETE** — `01b9b00b`, 42/42 corpus |
| PR-16..PR-20 RT-03..06 + docs | Landed `931f69f0` |
| PR-16..20 NAS deploy + live replay | **COMPLETE** — `931f69f0`, manifest promote, **47/47** required corpus |

## F. PR-16..20 live runtime (`931f69f0`)

```text
deploy_sha=931f69f04c697c4082f65fbf90ab2b6ae6c81af9
runtime_identity=exact_verified_commit
live_required_corpus=47/47 pass (fail_count 0)
manifest_version=7 workflow_count=15 surface_stale=false
schema_live_ro=119 workspace_rw=121
```

Detail: `09-pr16-20-operator-deploy-results.md`

## G. RT-01 Tier B clean rebuild (`542307fc`)

```text
deploy_sha=542307fc6fc87b7a5713b8917e861a576a03c96c
attestation_tier=CODE_VERIFIED_CLEAN_CONTEXT (Tier B)
runtime_identity_kind=exact_unverified_stamp (expected)
image_digest=sha256:2af0fd38265a8f592afcb9f08d0b4cf0083a3add1d1f051544bd95104ff0009b
tarball_bytes=105791674 (vs 193164199 Tier A dirty build)
```

Detail: `10-rt01-clean-rebuild.md` — operator deploy status updated after live replay.