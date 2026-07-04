# 11 — N5B / N5C Readiness (roadmap unchanged)

N5A does not redefine the roadmap. It unblocks the next sub-phases.

## N5B — scratch-root dry-run / availability proof (ready after N5A)
- Now possible because the NAS vault exists and the config drafts are authored.
- Runs **on-NAS**, as svc, read-only: `scripts/obsidian_source_root_availability_probe.py` (stat-only) against the NAS
  `vault_root` + the `syn-work` path, and `scripts/obsidian_source_first_indexing_dryrun.py` (no DB/card/queue writes).
- Proves NAS roots resolve/preview without ingestion. Uses the `app-support-smoke` root, not the copied production DB.
- **Note:** the availability probe was intentionally NOT run in N5A — the NAS path is not locally mounted here, and
  N5A's scope is mirror + drafts only. It belongs to N5B, run on the NAS.

## N5C — MSAL/Graph + Procore re-provision (determined; needs interactive login)
- Device-code `hb-assistant auth login` on the NAS → writes `<app-support>/auth/msal-token-cache.bin` (0600 svc);
  scopes include `Files.ReadWrite.All` (covers OneDrive/Graph `hb-onedrive`). Do not copy the Mac cache.
- Procore: client secret via env/protected file; mint fresh `<app-support>/auth/procore_token.json` (0600 svc);
  `HB_PROCORE_LIVE` stays off.

## Downstream (meanings unchanged)
- **N6** — NAS operator control tooling (benefits from the stable NAS vault path).
- **N7** — MCP-on-NAS via SSH launcher (needs the vault mirror + config; bearer/public-URL off by default).
- **N8** — second-brain / watchers / scheduler gating. **Gated by:** (1) the `source_root_key` identity fix before any
  multi-root activation; (2) a Linux scheduler to replace macOS `launchd`; (3) the Text Vault fail-closed startup
  preflight; (4) keep `syn-work` `read_only=True` while its path is mode `777`.
