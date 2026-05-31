# Phase 07C — Prompt 00: Repo-Truth Rebaseline

**Phase:** Construction Intelligence 07C — Document Intelligence Promotion
**Prompt:** 00 — Repo Truth Audit and 07B Gap Inventory
**Generated (UTC):** 2026-05-31
**Audit type:** Read-only rebaseline. No source/implementation files were edited; only this evidence pair was created.

> Leak-safety: this file contains command names, exit codes, repo SHA, schema version, and aggregate
> counts only. No raw document text, file names, web URLs, parent paths, signed/download URLs, tokens,
> secrets, raw email bodies, raw calendar payloads, raw prompts, raw responses, tenant GUIDs, or UPNs
> are reproduced here.

## 1. Repo Truth

| Item | Finding | Source |
|---|---|---|
| `git rev-parse HEAD` | `748ed7e6519ada0a74d09376f2d2fe353627ac2b` | exact match to package-audited commit |
| Ancestry vs audited commit | Identical (not a descendant — the audited commit *is* HEAD) | `git rev-parse HEAD` |
| `git status --short` | `?? .claude/` only | one untracked path |
| Dirty-file classification | `.claude/` is local Claude Code session config, **not** tracked repo source. No tracked files are modified, added, or deleted. | working-tree inspection |
| Package version | `1.3.0` | `pyproject.toml` `version`; `src/hb_assistant/__init__.py` `__version__` |
| Latest schema version (code) | `23` | `migrator.py` `LATEST_SCHEMA_VERSION = 23` |
| Default branch | `main` | repo |

## 2. Local SQLite State

DB path (outside repo, per `path_policy`): `~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`

| Item | Finding |
|---|---|
| `MAX(version)` in `schema_migrations` | `23` (rows 1…23 all present, contiguous) |
| `PRAGMA user_version` | `0` (repo uses the `schema_migrations` table, not the SQLite `user_version` pragma — consistent with all prior phases) |
| `construction_document_cards` rows | `0` (table exists, never populated) |
| `construction_drive_items` rows | `0` |
| `construction_drive_item_inventory` rows | `401` (file-intelligence inventory layer) |
| `construction_file_ingestion_decisions` rows | `0` |
| `construction_file_extraction_runs` rows | `0` |

## 3. Command Existence Preflight

All Prompt 00 validation commands resolve on this machine. No command was missing; therefore no
"missing command" was misclassified as a validation failure.

- `hb-assistant graph {files,calendar,mail}` subgroups present (`graph --help`).
- `hb-assistant construction-agent data-quality {gates,no-writeback-proof,table-inventory}` present.
- `hb-assistant graph files {status,no-writeback-proof}` present.

## 4. Validation Matrix

Every command below was executed in the project venv at HEAD `748ed7e`, schema version `23`.

| # | Command | Exit | Result summary |
|---|---|---:|---|
| 1 | `python -m compileall src tests` | 0 | All modules byte-compile. |
| 2 | `ruff check .` | 0 | `All checks passed!` (in-scope modules per `pyproject.toml`). |
| 3 | `mypy src` | 0 | `Success: no issues found in 164 source files`. |
| 4 | `pytest -m "not live and not integration and not manual"` | 0 | `1985 passed, 1 deselected in 105.78s`. |
| 5 | `hb-assistant construction-agent validate --json` | 0 | `ok=true`; schema=23; 6 projects / 14 sources; 25 review rules; model routing v1. |
| 6 | `hb-assistant procore validate --json` | 0 | `ok=true`; 28/28 checks passed; company 5280; 16 endpoints / 4 projects. |
| 7 | `hb-assistant graph files status --json` | 0 | `ok=true`; delegated; broad write scope `Files.ReadWrite.All` present; `permission_tightening=deferred`. |
| 8 | `hb-assistant graph files no-writeback-proof --json` | 0 | `ok=true`; guard self-test passed; 24 read paths allowed, 19 mutation attempts blocked. |
| 9 | `hb-assistant graph calendar status --json` | 0 | `ok=true`; `calendar_read_capability_present=true`; write-capable `Calendars.ReadWrite.Shared` present (endpoint guard enforces read-only). |
| 10 | `hb-assistant graph mail status --json` | 0 | `ok=true`; `mail_read_scope_present=true`; `forbidden_mail_scopes_requested=[]`. |
| 11 | `hb-assistant construction-agent data-quality gates --json` | 0 | 15 gates; repo_sha + schema=23 stamped; 0 blocking gates; readiness claims `blocked` (see §5). |
| 12 | `hb-assistant construction-agent data-quality no-writeback-proof --json` | 0 | `proof_passed=true`; 6 + 10 modules scanned; no findings. |
| 13 | `hb-assistant construction-agent data-quality table-inventory --json` | 0 | contract=96 / live=101; all 96 contract tables `present_in_db=true`. |

## 5. Readiness Claims (not overstated)

From `data-quality gates`:

- `meeting_prep_readiness_claim = blocked`
- `risk_digest_readiness_claim = blocked`
- 07D meeting-prep: `ready=false`, `auto_readiness_allowed=false`, `blocked_by = [document_card_population_status, review_required_routing_presence]`.
- 07C: `blocked_by = [document_card_population_status]`, `ready_for = [document_card_population, file_to_record_relationships]`.
- `raw_content_leakage_scan = pass`; `external_writeback_scan = pass`.

No gate or closeout overstates readiness; document-intelligence and meeting-prep remain correctly blocked.

## 6. Safety / Boundary Confirmation

- No mutation endpoint or write scope was exercised. Every command above is read-only or proof-only.
- No external-system writeback occurred (graph files + data-quality no-writeback proofs both pass).
- Broad write scopes are *consented at the tenant* but runtime guards enforce read-only:
  `Files.ReadWrite.All` (files) and `Calendars.ReadWrite.Shared` (calendar) are present-but-guarded,
  `permission_tightening=deferred` — carried forward as a disclosed residual risk (see gap audit §4).

## 7. Leak Scan

This evidence file was scanned before commit:

- No raw file names, web URLs, or parent paths (inventory raw fields summarized as counts only).
- No tokens, secrets, signed/download/tokenized URLs, or PEMs.
- No raw email bodies, calendar payloads, model prompts, or model responses.
- Tenant GUID and UPN observed in live CLI output were intentionally **not** reproduced.

## 8. Outcome

Repo truth matches the package-audited commit exactly; the working tree carries no tracked-source drift;
the full Prompt 00 validation matrix is green at HEAD `748ed7e`, schema `23`. No stop condition triggered.
