# PR-15 operator runbook — deploy + manifest + live corpus

**Live commit:** `542307fc6fc87b7a5713b8917e861a576a03c96c` (RT-01 Tier B — **deployed 2026-07-11**)  
**Previous NAS runtime:** `931f69f04c697c4082f65fbf90ab2b6ae6c81af9` (PR-16..20, Tier A)  
**Schema:** 119 (code-only deploy — no migration)

Closeout: `11-rt01-operator-deploy-results.md` · build record: `10-rt01-clean-rebuild.md`

| Artifact | Path | Size |
|----------|------|------|
| Image tarball | `/tmp/hb-nas-542307fc.tar.gz` | 105791674 bytes |
| Build manifest | `/tmp/hb-nas-542307fc.build-manifest.json` | |
| Deploy | `/tmp/01-deploy-pr15.sh` | |
| Manifest refresh | `/tmp/02-manifest-refresh-pr15.sh` | |
| Verify-only | `/tmp/03-manifest-verify-pr15.sh` | |
| Live 50-prompt corpus | `/tmp/04-live-50-prompt-corpus.sh` | |

Local tarball SHA-256: `f39e44dee8d75d8bfd3e5a93874f2e6ff501345e3a7b77068a26eb56ddbed014`

## 1. Deploy (sudo on NAS)

```bash
ssh -t hb-nas 'sudo sh /tmp/01-deploy-pr15.sh' | tee ~/deploy-pr15.txt
```

Pass criteria: step **6** runtime commit `542307fc…`, identity `exact_unverified_stamp`, digest populated, forbidden-path scan pass; step **7** may print `stale True` (expected until manifest refresh — proceed).

## 2. Manifest refresh (stage → promote)

**Important:** re-copy the script after any repo update — step 2 must bootstrap MCP registration
(`register_nas_mcp_tools`) before `pa_tool_manifest_refresh_stage`, or F-008 parity fails with
`schema_index_not_frozen`. NAS has no working `scp` — pipe over SSH instead:

```bash
ssh hb-nas 'cat > /tmp/02-manifest-refresh-pr15.sh' \
  < docs/evidence/nas-second-brain-n8c/20260711T063000Z-routing-remediation-closeout/02-manifest-refresh-pr15.sh
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

- **47 required** rows: `pass_count 47`, `fail_count 0`
- HIGH spot checks: rows 1, 25, 36 executable with expected `next_step` tools
- Full 50-row report may include `accepted_partial` informational failures

## 5. Capture closeout

Copy transcripts into this evidence folder and update `00-closeout.md` disposition to `DEPLOYED_AND_VALIDATED`.

**PR-16..20 status (2026-07-11):** complete — see `09-pr16-20-operator-deploy-results.md`.

## Rollback

```bash
ssh -t hb-nas 'sudo /usr/local/bin/docker tag hb-personal-assistant:prev hb-personal-assistant:nas && sudo /volume2/personal-assistant/bin/hb-mcp-runner restart'
```

Restore compose from the `.bak-*` file written in deploy step 0b if needed.