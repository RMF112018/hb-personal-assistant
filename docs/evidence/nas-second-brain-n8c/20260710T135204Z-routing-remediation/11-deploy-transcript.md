# Deploy transcript — routing remediation

**Date:** 2026-07-10  
**Deploy SHA:** `f53cba1c7b4bcba0c5d7bb82aa63694c3041f0e3`  
**Image tarball:** `/tmp/hb-nas-f53cba1c.tar.gz` on NAS (184M, sha256 `6cf6841a7368fff834b239860785b98a96f7f0f43a579fcf72d2d1cd175fb445`)  
**Image ID (Mac build):** `sha256:4172767daaccec3164c6cbc3a6f92b73ce9935d3390543fd5c30066b14ee433f`

## Completed (agent)

| Step | Status |
| --- | --- |
| Commit remediation stack | `f53cba1c` on `main` |
| `git push origin main` | see transcript below |
| Docker build `hb-personal-assistant:nas` | success |
| Transfer tarball to NAS | success (`gzip -t` ok on NAS) |
| Transfer deploy + probe scripts | `/tmp/hb-deploy-routing-remediation.sh`, `/tmp/hb-live-40-prompt-probe.sh` |

## Deploy outcome (2026-07-10 operator run)

Deploy and live probe **PASSED** after amd64 image rebuild. See `12-deploy-closeout.md` and `13-live-probe-summary.json`.

## Initial attempt (blocked)

```text
sudo: a terminal is required to read the password
```

NAS user `bfetting` is not in the `docker` group; deploy script must run as root.

## Operator commands (run now)

```sh
ssh -t hb-nas 'sudo sh /tmp/hb-deploy-routing-remediation.sh' | tee deploy-transcript.txt
ssh -t hb-nas 'sudo sh /tmp/hb-live-40-prompt-probe.sh' | tee live-40-probe.txt
```

Paste transcripts back into this bundle as post-deploy closeout when complete.