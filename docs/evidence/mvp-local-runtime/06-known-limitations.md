# Known Limitations — MVP Local Runtime (P06 + P07)

**Scope**: Consolidated, extractable limitations for the local-first MVP as of Phase 15 Prompt 07.  
**Sources**: P06 deterministic evidence harness + Prompt 07 operator runbook creation process + prior phase artifacts (targeted reference only).  
**Classification**: MVP_CANDIDATE_LOCAL_RUNTIME_READY (Graph delegated proof deferred pending admin consent).

## 1. Graph / Microsoft 365 Delegated Access (Prompt 9)

- Full delegated mail and calendar retrieval, plus the complete Prompt 9 capability proof, remain blocked until tenant admin consent is granted.
- When no valid delegated token is present, all `graph_*` stages correctly report `skipped_no_token` and local stages continue.
- No app-only flows are used or recommended for the real proof.
- Post-consent sequence is documented in `docs/plans/ph-15-MVP-Local-Runtime-Hardening/07_Deferred_Graph_Consent_Closeout_Runbook.md` (clear-cache → login → status → diagnostics graph/proof → scan-sensitive).

**Operator impact**: Many rich retrieval features are unavailable until IT completes consent. The local action extraction, body-mention detection, brief drafting, and marker-bounded Obsidian writes continue to provide value.

## 2. Dry-Run vs Apply Semantics (P03 / P06 Proven)

- Every high-level command that supports it defaults to or strongly encourages `--dry-run`.
- Dry-run paths are proven (P06 harness + prior evidence) to never mutate:
  - Microsoft 365
  - Obsidian notes (outside or inside markers)
  - `action_items`, `source_links`, parser outputs, etc. (beyond read-only ledger/evidence records when explicitly documented)
- Apply (non-dry-run) paths are intentionally narrow in the MVP.
- Obsidian writes (when they occur) are always strictly marker-bounded. User content placed outside `<!-- HB-DAILY-BRIEF:START -->` / `END` is never touched or duplicated (proven in P03 + P06 idempotency tests).

**Operator impact**: Safe daily use is via `--dry-run`. Apply paths require deliberate removal of the flag after review and should be used only when the operator understands the bounded write contract.

## 3. Automation / launchd

- Default schedule: 05:00 local (America/New_York), `catch_up: true`, `weekend_behavior: manual_only`.
- The LaunchAgent plist is not installed by default in a fresh clone.
- Uninstall is safe and previewable (`automation uninstall-launchd --dry-run`).
- The automation diagnostic (`diagnostics automation`) reports readiness, last ledger entry, and exact program arguments (using the repo's `.venv` python).

**Operator impact**: Weekend runs require manual invocation. The operator controls installation/uninstallation.

## 4. Local State Locations & Permissions (P05 / P07)

All local state lives under `~/Library/Application Support/HB Personal Assistant/` (or the configured `application_support_root`).

- DB: `db/hb-personal-assistant.sqlite`
- Auth/token caches: `auth/` (600 permissions)
- Logs: `logs/{run-logs, error-logs}`
- Evidence: `evidence/`
- Cache tiers: `cache/`, `cache/files/`, `cache/extracted-text/`, `cache/embeddings/`

The `diagnostics paths --repair-dry-run` command gives exact chmod recommendations and never executes sudo automatically.

**Operator impact**: These directories are inspectable. The operator should not manually edit the SQLite or token caches except via the documented CLI commands.

## 5. Redaction & Sensitive Data Boundaries (P04 / P06 / P07)

- Body mentions are stored and returned only as redacted excerpts + metadata (sender, subject, date, snippet). Full bodies are never persisted or surfaced.
- All diagnostics, evidence, and operator guide examples contain only redacted/synthetic data.
- The `diagnostics scan-sensitive` command is the mandatory gate before any commit or closeout.

**Operator impact**: The system is safe to point at real data for local processing because redaction is enforced at the storage and retrieval layers for body content.

## 6. Prompt 9 / Delegated Graph Proof (Deferred)

See section 1 and the dedicated 07_Deferred_Graph_Consent_Closeout_Runbook.md.

Until admin consent lands, the full end-to-end delegated proof cannot be executed. The local runtime (P06 harness + operator guide) is deliberately independent of this blocker.

## 7. Operator Guide & Evidence Artifacts (P07)

- The canonical non-code documentation is `docs/operations/mvp-local-runtime-operator-guide.md`.
- Internal phase runbooks/ are for implementers and were used only via targeted methods during P07.
- The 06-known-limitations.md (this file) and 07-operator-runbook-and-limitations.md are the process + limitations record for this prompt.

**Operator impact**: Always consult the published guide under `docs/operations/`. Do not rely on internal plan artifacts for daily operation.

## 8. Other MVP Limitations (Inherited / Reinforced)

- Action extraction in the current harness run produced low-confidence synthetic candidates because the P07 checks used a fresh temp-like environment with minimal seeded parser output. In real use the extractor improves as more local signals accumulate.
- Semantic retrieval / embeddings are gated and not exercised in the pure local dry-run proofs.
- Weekend + catch-up behavior is intentionally conservative.
- No write-back to Microsoft 365 is implemented in the MVP scope.

## How to Stay Current

1. Re-run `hb-assistant diagnostics env --json`, `diagnostics automation`, and `run morning --dry-run --json` periodically.
2. Re-run `diagnostics scan-sensitive` on any tree before committing evidence or changes.
3. When admin consent for Graph is granted, follow the exact sequence in the 07_Deferred_Graph_Consent_Closeout_Runbook.md and update this limitations document + the operator guide.
4. Any new safe CLI surface or behavioral change must be reflected in the operator guide and the two P07 evidence mds.

---

**Maintained as part of Phase 15 MVP Local Runtime Hardening Package.**  
Last updated during Prompt 07 on HEAD d15610e.  
Cross-references: P06 06-local-runtime-evidence-harness.md, 09_Source_Truth_Checklists.md (P06 + P07 flips), 07_Deferred_Graph_Consent_Closeout_Runbook.md.