# 01 — Preflight (carry-forward from N5A)

## Git posture at N5B start
- Branch `ops/nas-copied-db-n3-20260704T060648Z`, HEAD `2000e609` (`docs(nas): add N5A vault mirror config draft
  evidence`), working tree clean, **9 ahead** of `origin/main`, not pushed.
- N5A evidence **was committed** (`2000e609`); N5B evidence (this bundle) is generated fresh and left uncommitted.

## Commit chain (local only, never pushed)
```
2000e609 docs(nas): add N5A vault mirror config draft evidence
caf719d8 docs(nas): add N5 vault source roots planning evidence
58d09f50 docs(nas): add N4A text vault copy evidence
39961a35 docs(nas): add N4 secrets auth text vault evidence
761864ea docs(nas): add N3 copied DB smoke evidence
```

## Prerequisite verdicts confirmed present
- **N5 (planning) = PASS** — `docs/evidence/nas-vault-source-roots-n5/20260704T074519Z/` (files 00–14 present).
  Establishes: vault addressing is a single relative root (move transparent); source identity is rel_path-based
  (`source_index_repository.py:38`, omits `source_root_key` → N8 gate); `syn-work` NAS-native at
  `/volume1/homes/bfetting/Work` (mode 777 → keep read-only).
- **N5A = PASS** — `docs/evidence/nas-vault-mirror-config-draft-n5a/20260704T080459Z/` (files 00–12 + drafts +
  local-sensitive). NAS vault mirror placed (221 files / 155 md), owner `svc:users`, dirs 750 / files 640, svc-read
  proven; two non-activated config drafts; boundaries held.

## Execution model (unchanged)
- Agent runs non-sudo SSH (metadata-only reads; the agent key is in ssh-agent).
- Operator runs privileged NAS writes via interactive, password-gated `sudo`.
- All DB checks stay read-only; no `SQLiteMigrator.apply()` against production copied app-support.

## N5B scope confirmed against the runbook
Scratch-root setup + read-only/stat-only availability checks + non-activated config validation + evidence. No
production activation, ingestion, card generation, backend/MCP, schedulers, watchers, Cloudflare, or production DB
writes.
