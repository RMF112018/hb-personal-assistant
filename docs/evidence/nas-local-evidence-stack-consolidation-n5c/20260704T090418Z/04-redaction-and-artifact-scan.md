# 04 — Redaction & Artifact Safety Scan

Scanned committable evidence (`.md`/`.json`/`.yml`, excluding `local-sensitive/`) across the six NAS packages.

## Artifact scan (disallowed file types) — CLEAN
Zero of `.sqlite`, `.sqlite-wal`, `.sqlite-shm`, `.enc`, `.key`, `.tar`, `.zip`, `token*`, `.bin`, `.pem` are tracked
in any of the six NAS packages. No raw runtime artifacts, DB/WAL/SHM files, key material, blobs, token caches, or
tarballs. No files > 256 KB.

## Redaction grep — CLEAN except one documented pre-existing finding
(Pattern names only; literal sensitive values are not reproduced in committable evidence.)

| Pattern | Result |
|---|---|
| Mac home-dir absolute path (`mac-home` prefix) | **1 hit** — pre-existing N3 (see below) |
| tailnet IP | clean |
| WAN IP | clean |
| private-key markers | clean |
| full 64-hex hash | clean |
| full 32-hex Text Vault ref | clean |
| access/refresh-token assignment | clean |
| bearer-token literal | clean |

### The single legacy finding (pre-existing, low-sensitivity, not a new N5C leak)
- **Location:** `docs/evidence/nas-copied-db-n3/20260704T060648Z/02-live-db-source-proof.md:3` — the live Mac DB
  absolute path under the Mac home directory (`<mac-home>/Library/Application Support/HB Personal Assistant/db/…`;
  literal path only in `local-sensitive/`).
- **Nature:** already-committed N3 historical evidence (commit `761864ea`); the standard macOS Application Support
  location (also documented in `CLAUDE.md`). **Not** a secret, token, key, hash, or ref.
- **Disposition:** left **unchanged** — per §6 prior factual findings are not modified without explicit
  evidence-maintenance authorization. Carried as an optional redaction-maintenance item (`07`). It is not a new leak
  and does not fail the consolidation gate.

## Negative attestations (acceptable)
Committable files contain phrases like "no bearer token" / "no secrets" / "contains NO secrets" — these are negative
attestations, not secret material.

## Net
Redaction posture is clean for all new/relevant content; the one legacy Mac home-dir path is documented and deferred.
Sensitive operational detail lives only in the git-ignored `local-sensitive/` dirs.
