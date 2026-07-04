# 01 — Preflight (carry-forward from N5)

## Git posture at N5A start
- Branch `ops/nas-copied-db-n3-20260704T060648Z`, HEAD `caf719d8` (`docs(nas): add N5 vault source roots planning
  evidence`), working tree clean, **8 ahead** of `origin/main`, not pushed. Matches expected (N3 761864ea → N4
  39961a35 → N4A 58d09f50 → N5 caf719d8).

## Established prerequisites (unchanged)
- **N3** — copied DB placed at `/volume1/personal-assistant/app-support/db/hb-personal-assistant.sqlite`
  (`-rw------- personal-assistant-svc:users`), quick_check/integrity ok, schema 98. PASS.
- **N4A** — Text Vault key + `.enc` blobs on NAS under `<app-support>/security/`; coherence proved (COHERENT=YES).
- **N5 (planning)** — PASS. Established: vault addressing is a single relative `obsidian_vault` root (move is
  transparent); notes are content-safe (relative `source_path`/`source_root_key`, no absolute Mac paths); source
  identity is rel_path-based (`source_index_repository.py:38`); `syn-work` is NAS-native at
  `/volume1/homes/bfetting/Work` (operator-confirmed, mode `777` → register `read_only=True`).

## Execution model (unchanged from N3/N4A)
- Non-privileged agent work over SSH exec channel (no SFTP subsystem on the NAS).
- Privileged NAS writes performed by the operator via interactive, password-gated `sudo`.
- Dedicated passphrase-protected agent-only key via ssh-agent; sudo is never NOPASSWD.

## N5A scope confirmed against the runbook
Mirror the vault to `/volume1/personal-assistant/vault/obsidian` (owner `personal-assistant-svc:users`, dirs `750`,
files `640`); produce non-activated config drafts; prove equivalence + svc-read; redacted evidence; leave uncommitted
unless separately authorized. Do **not** copy `syn-work` (NAS-native already), and do **not** activate anything.
