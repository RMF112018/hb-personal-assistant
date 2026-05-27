# MVP Local Runtime Operator Guide

**Purpose**: Run, inspect, troubleshoot, and safely operate the HB Personal Assistant local-first MVP without reading source code.

**Audience**: Bobby (the human operator).  
**Assumptions**: You have the repo cloned at `~/hb-personal-assistant` and the Python virtual environment created (`.venv`).

**Classification**: MVP_CANDIDATE_LOCAL_RUNTIME_READY (Graph delegated proof deferred pending admin consent).

**Safety First**
- Prefer `--dry-run` for all exploration and daily use.
- The system is designed so that dry-run paths never mutate your Obsidian vault, the local SQLite store (beyond run ledger/evidence), or Microsoft 365.
- Graph-dependent features are explicitly skipped when no delegated token is present and are documented as such.
- Never run commands that claim to write to Microsoft 365 unless you have explicit delegated consent and understand the scope.

## 1. Activate the Environment

```bash
cd ~/hb-personal-assistant
source .venv/bin/activate
```

After activation your prompt should show the venv. All `hb-assistant` commands below assume the venv is active (or you use the full `.venv/bin/hb-assistant` path).

Deactivate with `deactivate` when finished.

## 2. Run Diagnostics (Safe, Read-Only)

The `diagnostics` command group is the primary inspection tool.

```bash
# Environment and important local paths
hb-assistant diagnostics env --json

# Detailed path permissions + repair guidance (dry-run)
hb-assistant diagnostics paths --repair-dry-run

# Launchd / automation readiness (05:00 local, catch-up behavior, weekend manual_only)
hb-assistant diagnostics automation

# Sensitive artifact scan over a tree (example: evidence dir)
hb-assistant diagnostics scan-sensitive --repo docs/evidence/mvp-local-runtime --json

# Auth / token cache status (delegated by default)
hb-assistant diagnostics auth --json

# Store summary (redacted counts only)
hb-assistant diagnostics store --json
```

These commands never transmit secrets or full content. Use them freely for daily health checks.

## 3. Run Morning Workflow (Dry-Run Recommended)

```bash
# Safe daily dry-run (recommended for routine use)
hb-assistant run morning --dry-run --json

# You will see stages such as:
# - path_readiness / store_readiness
# - graph_* stages → "skipped_no_token" (expected while consent pending)
# - local_signal_load, classification, action_extraction, workstream_context, etc.
# - brief_draft and obsidian_write_dry (marker-bounded, no vault mutation in dry-run)
```

The dry-run produces a full JSON report of what *would* happen. Local stages continue even when Graph is unavailable.

## 4. Apply / Write Mode (Use With Caution)

Most high-level commands default to safe modes. True apply/write behavior is intentionally limited and clearly labeled.

- `run morning` without `--dry-run` will attempt the full flow (still respects Graph consent gate and marker-bounded Obsidian writes).
- File ingestion (`files ingest`) supports `--dry-run`.
- Obsidian writes are always marker-bounded (`<!-- HB-DAILY-BRIEF:START --> ... <!-- HB-DAILY-BRIEF:END -->`). Content you place outside those markers is never touched.

**Recommendation**: Run with `--dry-run` first, review the JSON, then remove the flag only when you are confident and have a recent backup of your vault.

## 5. What Gets Written Locally (Apply Paths)

When you run without `--dry-run` and the system has data:

- Run ledger entries and evidence JSONs under the app support `evidence/` directory.
- Source links in the local SQLite (for provenance of actions written to notes).
- Marker-bounded sections inside your Obsidian Daily Notes (only between the HB markers).
- Cache files (extracted text, embeddings) under app support `cache/`.
- Error and run logs under app support `logs/`.

Nothing is written to Microsoft 365 unless you have a valid delegated token *and* the specific command is designed for write (currently very limited in the MVP).

## 6. What Never Gets Written

- Full email bodies or calendar event bodies (only redacted excerpts or metadata).
- Any data to Microsoft 365 without explicit delegated consent and the correct command path.
- Content outside the HB daily brief markers in your Obsidian notes.
- Action items or source links during any `--dry-run`.
- Secrets, tokens, or PEMs into logs or evidence (enforced by the sensitive scanner).

## 7. Where Logs and Evidence Live

Default locations (from `diagnostics env` / `paths`):

- App support root: `~/Library/Application Support/HB Personal Assistant`
- Logs: `.../logs/` (run-logs, error-logs)
- Evidence: `.../evidence/`
- Run ledger and diagnostic JSONs are written here during automation or manual runs.

You can safely inspect these directories. The sensitive scanner can be pointed at them.

## 8. Where SQLite, Auth, and Cache Files Live

From `diagnostics env --json` and `paths`:

- SQLite DB: `.../db/hb-personal-assistant.sqlite`
- Auth / token cache: `.../auth/` (files are 600 permissions)
- Cache (extracted text, embeddings, files): `.../cache/`, `.../cache/files/`, `.../cache/extracted-text/`, `.../cache/embeddings/`

These are all local-only. The auth directory contains MSAL token caches for delegated (and optional app-only proof) flows.

## 9. How to Disable launchd Automation

```bash
# Preview (safe)
hb-assistant automation uninstall-launchd --dry-run

# Actual removal
hb-assistant automation uninstall-launchd
```

This runs (approximately):
```bash
launchctl unload -w ~/Library/LaunchAgents/com.hb.personal-assistant.morning.plist
rm -f ~/Library/LaunchAgents/com.hb.personal-assistant.morning.plist
```

After uninstall the 05:00 automated morning run will stop. You can still invoke `run morning` manually.

Re-install with `hb-assistant automation install-launchd` (supports `--dry-run`).

## 10. How to Inspect Errors

1. Run the failing command with `--json` and capture the output.
2. Check recent files in `~/Library/Application Support/HB Personal Assistant/logs/error-logs/`.
3. Run `hb-assistant diagnostics env --json` and `diagnostics paths` to rule out permission or path issues.
4. Run `hb-assistant diagnostics scan-sensitive --repo . --json` (or a subdirectory) if you suspect a leak or malformed artifact.
5. For automation issues: `hb-assistant diagnostics automation` (shows last ledger entry and readiness).

## 11. What Remains Blocked by IT / Admin Consent

- Full delegated Microsoft Graph mail and calendar access (Prompt 9).
- Any feature that requires live `graph_retrieval` or `graph_*` stages when no valid delegated token is cached.
- The system gracefully degrades: local stages (action extraction from parser output + body-mention signals, workstream context, brief drafting, marker-bounded Obsidian writes) continue to function.

Current classification in all evidence: `GRAPH_DELEGATED_PROOF_DEFERRED_PENDING_ADMIN_CONSENT`.

## 12. How to Run Prompt 9 (Delegated Graph Proof) After Consent Is Granted

See the dedicated internal runbook for the exact post-consent sequence:

`docs/plans/ph-15-MVP-Local-Runtime-Hardening/07_Deferred_Graph_Consent_Closeout_Runbook.md`

High-level steps (after admin consent is confirmed):

```bash
source .venv/bin/activate
hb-assistant auth clear-cache --json
hb-assistant auth login --json          # follow the device code / browser flow
hb-assistant diagnostics auth --json
hb-assistant diagnostics graph --safe --json
hb-assistant diagnostics proof delegated-graph --json
hb-assistant diagnostics scan-sensitive --repo . --json
```

Only proceed with the full Prompt 9 proof once the delegated token is confirmed healthy and the tenant admin consent is in place. Do not use app-only flows for the real proof.

## Quick Reference Commands

| Goal                        | Command (with venv active)                          | Safe?     |
|-----------------------------|-----------------------------------------------------|-----------|
| Activate env                | `source .venv/bin/activate`                         | Yes       |
| Health check                | `hb-assistant diagnostics env --json`               | Yes       |
| Paths & permissions         | `hb-assistant diagnostics paths --repair-dry-run`   | Yes       |
| Automation / launchd status | `hb-assistant diagnostics automation`               | Yes       |
| Daily dry-run               | `hb-assistant run morning --dry-run --json`         | Yes       |
| Action extraction dry-run   | `hb-assistant actions extract --dry-run --json`     | Yes       |
| Uninstall launchd           | `hb-assistant automation uninstall-launchd --dry-run` | Preview |
| Sensitive scan              | `hb-assistant diagnostics scan-sensitive --repo <path> --json` | Yes |
| Post-consent Graph proof    | See section 12 + the 07_Deferred_Graph runbook      | After consent |

## Known Limitations & Future Work

- Graph mail/calendar retrieval and full Prompt 9 proof are blocked until tenant admin consent is granted.
- Apply (non-dry-run) paths are intentionally narrow in the MVP and always respect marker boundaries in Obsidian.
- Weekend behavior is `manual_only` by design.
- The operator guide and evidence artifacts are the canonical non-code documentation. Internal phase runbooks are for implementers.

For the full extracted limitations list (including P06 harness limitations and operational ones surfaced during guide creation), see:

`docs/evidence/mvp-local-runtime/06-known-limitations.md`

---

**Maintained as part of Phase 15 MVP Local Runtime Hardening Package.**  
Update this guide when new safe CLI surface or operational behavior is added. Always validate changes with `--dry-run` + the sensitive scanner before committing.