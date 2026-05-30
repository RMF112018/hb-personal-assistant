# HB Personal Assistant + Work Product Intelligence System

Bobby-only local-first MVP for Microsoft 365 delegated access, source-linked retrieval, action intelligence, meeting prep, file review, and Obsidian Daily Brief output.

**The Daily Brief is a module, not the project name.**

## Repository Status

**Phase 01 (scaffold completion).** Construction-intelligence scaffold landed across Phase 01 Prompts 00–11 ending at SHA `34728c1`: Pydantic source registry + YAML loaders; V1–V4 additive SQLite schema (`construction_source_resolutions`, `construction_drive_item_inventory`, review queue, model decisions); Graph delta crawler with redacted error envelopes; Obsidian manifest / receipt / projection layer with the delta-link-fingerprint never-leaks invariant; deterministic review-queue policy with controller-overrides-model router; Ollama classification with `--mock-output` offline mode; Procore endpoint contract + auth-status stub; full operator CLI surface; baseline 240 passing tests. See `docs/evidence/construction-intelligence-phase-01/`.

**Phase 02 (corrective alignment).** Phase 02 Prompts 00–10 landed at HEAD `9564ee2`: source registry expanded from 3 sources / 2 projects to 14 sources / 6 projects via a Pydantic alias bridge (Phase 01 records preserved verbatim); V5 canonical SQLite schema with 10 additive tables + hard `CHECK` constraints on `read_only` / `mailbox_writeback_allowed` / `persist_full_body` invariants; folder-scoped Graph delta resolution + Hilltop ProjectHome linked-source discovery (no deep-index escape); Tropical baseline-comparison primitive against the canonical 8921-item / 39.78 GB inventory; OneDrive inventory-first policy + 4 PII review rules (12 → 16); Procore mapping corrected (`tropical: 23-435-01` → `2525840`) with `^\d{2}-\d{3}-\d{2}$` HB-number-shape validator and seed expanded 2 → 6 projects; Obsidian output hardening (`raw_delta_link_redacted` attestation, canonical `source_id` frontmatter alias, 7-output guardrail fence covering body-text / delta-link / token-shaped-secret); Ollama live-readiness probe via new `construction-agent ollama status` (offline-CI-safe, no live inference); email-intelligence deferred-foundation policy with Pydantic `Literal[False]` / `Literal[True]` guards and mailbox-mutation lockout static scans; closeout test count 413, ruff clean. See `docs/evidence/construction-intelligence-phase-02/`.

**Remaining external validation.** The following live validations were not exercised in any Phase 02 prompt and remain explicitly blocked or stubbed: live MSAL-backed Graph delta crawl against Tropical (requires interactive shell); live Procore OAuth + `/vapid/projects` round-trip (Procore HTTP client intentionally absent — `test_procore_module_imports_no_http_client` enforces this); live Ollama daemon presence (the readiness probe is exercised via mocked `requests.get` plus one offline `ollama status` invocation reporting `daemon_unreachable`); live mailbox metadata fetch — mailbox stays read-only at four layers (YAML policy, MSAL scope, Python adapter, SQLite CHECK), and although `Mail.ReadWrite.All` is granted at the tenant level, `IdentityConfig.delegated_scopes` continues to request only `Mail.Read`. The 4 pre-existing `test_obsidian_writer.py` failures noted in the Phase 01 final-closeout summary persist; they predate Phase 02 and are out of scope.

**Phase 05 (Procore Contracts & Financials) — Closed.** Phase 05 Prompts 01–12 landed at closeout SHA `6d77d35` (closeout commit follows): the Procore subsystem extends into the contract / financial-control surface (owner contracts, commitments, purchase orders, subcontractor invoices, RFQs, change events, budget) via the `procore/endpoints.py` registry (59 endpoints = 27 Phase 04A/04B operational + 32 financial), per-family normalizers + redaction utilities, additive **V9** SQLite schema (15 `procore_financial_*` projection tables + amount-facts ledger; V9 added billing periods + subcontractor invoices), the fail-closed live gate, generalized N+1 parent→child orchestration with parent-id tagging, 7 SQLite-only financial query commands + an Obsidian financial register, and a probe-first live-promotion pass against the `tropical` pilot (procore_project_id 2525840, company 5280, GET-only) that promoted **29** financial endpoints. Posture: **56 / 59 endpoints live-verified**, **3 fail-closed** (`purchase-order-detail-line-items` per-PO 404 data condition, `budget-change-line-items` 403 permission grant, `budget-details` unresolved-path sentinel) — documented as a deferred remediation list. Closeout validation green (pytest exit 0; ruff / `mypy src` / compileall clean; `procore validate` 28/28; no-secret probe over 2209 financial rows = 0 findings, `raw_body_persisted=0` / `redaction_applied=1`). No Microsoft 365 or Procore writeback. See `docs/evidence/construction-intelligence-phase-05-financials/` (Prompts 00–12) and `docs/architecture/16-procore-financials-phase-05.md`.

**Phase 06A (SharePoint / OneDrive File Intelligence) — In progress (Prompts 00–15).** A read-only delegated-Graph file-intelligence surface under `hb-assistant graph files`: operator `status` + `no-writeback-proof`; canonical V5 source projection (`sources`); SharePoint site/drive + OneDrive discovery (`sites`, `site resolve`, `drives`, `onedrive`); user-provided-link → canonical-ID resolution via the read-only Shares API (`link resolve`, no sharing-link redemption); rich driveItem metadata indexing, bounded baseline crawl, and hardened incremental delta sync (`index`, `crawl`, `delta`); project-aware file matching (`project-match`); pre-fetch ingestion-eligibility policy (`ingestion-policy`); controlled drive-aware download + **bounded redacted** extraction (`extract`, requiring explicit `--download`/`--extract`); sensitive-file review routing (`review-queue`); grouped marker-bounded Obsidian manifests/registers/review-summaries/receipts (`obsidian`); and source-linked retrieval over bounded excerpts (`retrieve`). Additive **V15–V19** SQLite schema (rich driveItem index, link resolution, project-match fields, `construction_file_ingestion_decisions` with the `review_required → no extraction` CHECK, download-receipt + extraction-run tables with `full_text_persisted = 0` / `source_file_copied_to_vault = 0` / `raw_download_url_persisted = 0` CHECKs). Guardrails: **dry-run is the default** for every write-capable command; side effects require explicit `--apply`/`--download`/`--extract`; no Microsoft 365 writeback; no source files copied into Obsidian; no full document text, signed URLs, `@microsoft.graph.downloadUrl`, or raw delta links persisted (delta links surface only as SHA-256 fingerprints); review-routed files cannot extract. **Deferred:** broad `Files.ReadWrite.All` consent is retained and **not** tightened in this phase — a documented risk (`docs/evidence/construction-intelligence-sharepoint-onedrive/22-deferred-permission-tightening-record.md`); the runtime stays read-only at four layers. Operator runbook: `docs/runbooks/phase-06a-operational-sharepoint-onedrive-workflows.md`. See `docs/evidence/construction-intelligence-sharepoint-onedrive/` and `docs/architecture/18-sharepoint-onedrive-file-intelligence-phase-06.md`.

## Quickstart (after clone)

```bash
# Use the phase-0 venv or create fresh
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

hb-assistant --version
hb-assistant --help
hb-assistant diagnostics env --json
```

## Key Paths (macOS)

- Application Support: `~/Library/Application Support/HB Personal Assistant/`
- Obsidian Vault: `/Users/bobbyfetting/Documents/Obsidian Vault/`

See `docs/architecture/` for implementation and remediation records, and `docs/plans/my-pa-phase-0/` for the original implementation package.

## Guardrails (Global)

- Delegated Bobby-user Microsoft Graph auth is the runtime default.
- Certificate-backed app-only is proof/admin only.
- **No** Microsoft 365 write-back.
- **No** tokens/keys/full bodies/PEMs logged or committed.
- Store auth/cache/SQLite/logs **outside** the repo.
- Dry-run before writes.
- Every output carries source traceability.

## Construction Intelligence Phase 02 Status

Phase 01 closed as a construction-intelligence scaffold / foundation. Phase 02 Prompts 00–10 landed corrective alignment across the source registry, the canonical V5 SQLite schema, folder-scoped Graph resolution + Hilltop linked-source discovery, the Tropical baseline-comparison primitive, the OneDrive inventory-first policy + PII review rules, the Procore project mapping (HB-number-shape rejected), the Obsidian output projection layer (redaction proof + `source_id` alias + 7-output guardrail fence), Ollama live-readiness, and the email-intelligence deferred-foundation policy.

- Phase 02 evidence: `docs/evidence/construction-intelligence-phase-02/` (12 files at closeout: Prompts 00–10 + this closeout).
- Local validation: 413 pytest passing; ruff clean across `src/hb_assistant/construction/`, `src/hb_assistant/procore/`, and the construction + procore CLI modules; `construction-agent validate --json` reports `ok` across schema / source_registry / review_rules / model_routing.
- Live external validation status: live Graph delta crawl, live Procore OAuth, live Ollama daemon probe, and live mailbox metadata fetch all remain pending — see *Remaining external validation* in the Repository Status block above. The granted-but-suppressed mailbox posture (Mail.ReadWrite.All consented at tenant level; `Mail.Read` is the runtime-requested scope) is documented at `docs/evidence/construction-intelligence-phase-02/10-email-intelligence-deferred-foundation.md`.

## Email Intelligence (Deferred)

`Mail.ReadWrite.All` has been granted at the tenant level but is intentionally suppressed for Phase 02. Mailbox writeback and full-body persistence are locked at four layers:

- **Pydantic policy** — `resources/config/email_intelligence_deferred_policy.yaml`, loaded via `hb_assistant.construction.policy.load_email_intelligence_deferred_policy()`, enforces `mailbox_writeback_allowed: false`, `persist_full_body: false`, and `review_required_for_sensitive: true` via `Literal[False]` / `Literal[True]` fields.
- **MSAL scope request** — `IdentityConfig.delegated_scopes` requests only `Mail.Read` at token acquisition. `Mail.ReadWrite.All` and `Mail.Send` are never asked for at runtime, even though the tenant has consented to the broader scope.
- **Python adapter** — `ConstructionStore.set_email_intelligence_deferred_state` raises if either locked flag is set to `True`.
- **SQLite** — V5 table `construction_email_intelligence_deferred_state` carries SQL `CHECK` constraints on the locked-false fields and a singleton `id = 1` row.

Full email-intelligence activation is deferred to a future phase.

## Validation & Evidence

Authoritative construction-intelligence evidence lives in two directories:

- `docs/evidence/construction-intelligence-phase-01/` — 12 files including session handoff and final closeout summary (Phase 01 scaffold).
- `docs/evidence/construction-intelligence-phase-02/` — 12 files at closeout (Phase 02 Prompts 00–10 + truthfulness closeout).

Each Phase 02 prompt has a dedicated evidence artifact (e.g. `07-procore-mapping-correction-and-audit-readiness.md`, `08-obsidian-output-quality-proof.md`, `09-review-policy-and-ollama-live-readiness.md`, `10-email-intelligence-deferred-foundation.md`); per-prompt narratives live there rather than in this README.

## Historical Evidence

Earlier remediation-addendum and Phase 14 evidence remains in-tree at its original paths for audit continuity. Those records are historical and are superseded for current construction-intelligence work by the Phase 01 and Phase 02 evidence directories.

- `docs/evidence/remediation-addendum/`
- `docs/evidence/phase-14-local-runtime-workstream-intelligence/`
- `docs/evidence/remediation/remediation-baseline.md` (prior remediation baseline)
