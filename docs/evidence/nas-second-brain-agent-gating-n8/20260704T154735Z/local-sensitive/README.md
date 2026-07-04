# local-sensitive/ (N8) — gitignored, never committed

This directory holds raw runtime outputs and any NAS-specific identifiers that must **not** enter git
history. It is ignored by `.gitignore` (`/local-sensitive/` and `docs/evidence/**/local-sensitive/`).

## What belongs here (only when the live proofs 04–07 run, with Bobby)
- Raw NAS runtime config with the resolved `nas_test` source root + vault path (and its sha for the
  committed evidence to reference by hash only).
- Raw SSH / compose / backend logs from the bounded ingestion + card proofs.
- Raw `PRAGMA`/row-count command output that contains absolute NAS paths or the tailnet host/IP.
- The lock/lease payloads captured live (they contain the NAS hostname).

## What must NEVER be here or in committed evidence
- Token values, client secrets, `id_token`/`access_token`/`refresh_token`, MSAL cache contents.
- Text-Vault key / Fernet key, private keys / PEMs, tunnel or service-token secrets.
- Decrypted confidential document text.

## This session
Empty — no live NAS proof ran (Phases 04–07 are on HOLD pending Bobby's per-step approval). Committed
N8 evidence references NAS parameters by name/structure only and carries no secrets (see `08`).
