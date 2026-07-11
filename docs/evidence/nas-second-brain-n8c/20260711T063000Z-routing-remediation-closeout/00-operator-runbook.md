# PR-15 operator runbook — deploy + manifest + live corpus

**Land commit:** `01b9b00bb2e79a6523397073152b56fe14c01527` (PR-1..PR-14)  
**Previous NAS runtime:** `f565b19b1525fbeef75077c53be2b3bb0520c274`  
**Schema:** 119 (code-only deploy — no migration)

Artifacts are **already staged on the NAS** under `/tmp/` (2026-07-11).

| Artifact | Path | Size |
|----------|------|------|
| Image tarball | `/tmp/hb-nas-01b9b00b.tar.gz` | 193131985 bytes |
| Deploy | `/tmp/01-deploy-pr15.sh` | |
| Manifest refresh | `/tmp/02-manifest-refresh-pr15.sh` | |
| Verify-only | `/tmp/03-manifest-verify-pr15.sh` | |
| Live 50-prompt corpus | `/tmp/04-live-50-prompt-corpus.sh` | |

Local tarball SHA-256: `c93ee1caf2fa59328ea3448c7d76a41442fd71c89fc6ae49790e3eb6fda836de`

## 1. Deploy (sudo on NAS)

```bash
ssh -t hb-nas 'sudo sh /tmp/01-deploy-pr15.sh' | tee ~/deploy-pr15.txt
```

Pass criteria: step **6** runtime commit `01b9b00b…`; step **7** `stale False` (may remain stale until manifest refresh — proceed).

## 2. Manifest refresh (stage → promote)

```bash
ssh -t hb-nas 'sudo sh /tmp/02-manifest-refresh-pr15.sh' | tee ~/manifest-refresh-pr15.txt
```

Pass criteria: `workflow_count 15`; `tool_manifest_stale False`; step **4b** surface `stale false`.

## 3. Verify-only (optional double-check)

```bash
ssh -t hb-nas 'sudo sh /tmp/03-manifest-verify-pr15.sh' | tee ~/manifest-verify-pr15.txt
```

## 4. Live 50-prompt corpus replay

```bash
ssh -t hb-nas 'sudo sh /tmp/04-live-50-prompt-corpus.sh' | tee ~/live-corpus-pr15.txt
```

Pass criteria:

- **42 required** rows: `pass_count 42`, `fail_count 0`
- HIGH spot checks: rows 1, 25, 36 executable with expected `next_step` tools
- Full 50-row report may include `accepted_partial` informational failures

## 5. Capture closeout

Copy transcripts into this evidence folder and update `00-closeout.md` disposition to `DEPLOYED_AND_VALIDATED`.

## Rollback

```bash
ssh -t hb-nas 'sudo /usr/local/bin/docker tag hb-personal-assistant:prev hb-personal-assistant:nas && sudo /volume2/personal-assistant/bin/hb-mcp-runner restart'
```

Restore compose from the `.bak-*` file written in deploy step 0b if needed.