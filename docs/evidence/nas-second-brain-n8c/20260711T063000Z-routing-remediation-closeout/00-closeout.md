# Routing audit remediation closeout (PR-15)

**Date:** 2026-07-11  
**Disposition:** `DEPLOYED_AND_VALIDATED` — operator closeout complete (2026-07-11, verify r4)

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
| PR-15 deploy + manifest + live replay | **COMPLETE** — deploy, manifest R4, 42/42 corpus, verify r4 all PASS |