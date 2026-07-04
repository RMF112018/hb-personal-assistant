# 09 — Text Vault Decrypt Smoke Plan (deferred; do not execute without authorization)

## Purpose
Prove key↔blob↔DB works end-to-end on NAS by decrypting a tiny sample — beyond the existence/count coherence already
proven in N4A. Optional; not required for N4A/N5.

## Requirements if authorized (N5B or a dedicated N5-smoke)
- Run as `personal-assistant-svc` against the **`app-support-smoke` scratch root**, not the production copied
  app-support root (unless repo-truth proves the path strictly read-only). Never open the copied DB writably; never
  invoke `SQLiteMigrator.apply()`.
- Do NOT print or write decrypted text. Print only: `decrypt_smoke=ok`, plaintext length, optionally a redacted
  ref-category count. No raw refs, no plaintext, no hashes.
- No backend/MCP start; no note/card workflows; no auto-migration.

## Default
Existence/count coherence (N4A) is sufficient; **defer decrypt smoke**. If any doubt, run in a dedicated smoke phase
on the scratch root. Not executed this pass.
