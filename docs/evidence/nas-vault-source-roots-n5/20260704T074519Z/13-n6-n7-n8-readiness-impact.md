# 13 — Roadmap Readiness Impact

Roadmap phases (established; N5 does not redefine them):

## N5 sub-phases (this workstream)
- **N5A — authorized vault mirror + non-activated config draft implementation.** Ready pending authorization. Vault is
  LOW-risk (4.9 MB, relative, content-safe). Produces the NAS vault copy + config drafts (not activated).
- **N5B — scratch-root dry-run / availability proof.** Ready after N5A. Uses `app-support-smoke` + stat-only
  availability probe + first-indexing dry-run (no DB/card writes). Proves NAS roots resolve without ingestion.
- **N5C (or later authorized phase) — MSAL/Graph and Procore re-provision proof.** Commands determined (08); needs
  device-code login + Procore secret; writes only to `<app-support>/auth/` (0600 svc). Unblocks `hb-onedrive`/Graph roots.

## Downstream phases (unchanged meanings)
- **N6 — NAS operator control tooling.** Unaffected by N5 planning; benefits from a stable NAS path map.
- **N7 — MCP-on-NAS via SSH launcher.** Needs the vault mirror + config (N5A) so MCP can read notes/roots as svc;
  bearer/public-URL remain off by default.
- **N8 — second-brain / watchers / scheduler gating.** **Gated by two hardening items** before activation:
  (1) the source-identity `source_root_key` fix (04/10) — required before any multi-root NAS activation to avoid
  cross-root collisions; (2) a Linux scheduler to replace macOS `launchd`. Also requires the Text Vault fail-closed
  startup preflight (10) before production runtime.

## N8 activation guardrails (carry-forward)
- Fix the `source_id`-omits-`source_root_key` defect before any multi-root activation (04/10).
- `syn-work` root `/volume1/homes/bfetting/Work` is mode `777` → FS does not enforce read-only; keep it registered
  `read_only=True` and run no write-capable workflow against it unless perms/bind-mount are tightened separately.
- Replace macOS `launchd` with a Linux scheduler; add the Text Vault fail-closed startup preflight (10).

## Net
N5A/N5B are unblocked for separate authorization; N5C determined; N8 activation blocked pending the identity fix +
scheduler replacement + Text Vault startup guard + the `read_only` guardrail above.
