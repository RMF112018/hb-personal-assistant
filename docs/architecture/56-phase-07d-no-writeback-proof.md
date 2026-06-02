# 56 — Phase 07D: No-Writeback / No-Secret / No-Raw-Content Proof (07D arm)

**Status:** Implemented (Phase 07D Prompt 13; CLI alias added Phase 08A Prompt 01). Additive over schema **V25** (no migration).
**Scope:** Extend the formal `build_data_quality_no_writeback_proof`
(`construction/data_quality/safety.py`) with a Phase 07D arm so the existing
`construction-agent data-quality no-writeback-proof` command now proves no external writeback / no
secret / no raw content across all of 07D as well as 07A/07B/07C. Read-only, fail-closed.

## Design

The proof is built from reusable per-phase scan helpers; the 07D arm mirrors the 07C arm exactly:

| Check (07D) | Helper | Surface |
|---|---|---|
| `static_writeback_scan_07d_modules` | `_scan_module_set` | nine 07D modules — mutation verbs (regex + AST `.post/.put/.patch/.delete/.send/.create/.update/.share/.invite`) |
| `no_http_client_or_mutation_imports_07d` | `_scan_module_set` | dangerous imports (requests/httpx/aiohttp/procore/msgraph/msal) |
| `module_secret_scan_07d` | `_scan_text_for_secrets` | value-shaped secret patterns in module source |
| `sqlite_guard_checks_07d_cross_source_tables` | `_probe_table_guards` | the ten V25 tables × eight guard `CHECK(…=0)` columns |
| `sqlite_content_leak_scan_07d_cross_source_tables` | `_scan_table_contents` | safe text columns vs `_RAW_LEAK_PATTERNS` (url/email/ical) + secret patterns |
| `evidence_output_scan_07d` | `_scan_evidence_outputs` | the 07D evidence tree |
| `obsidian_output_scan_07d` | `_scan_obsidian_outputs` | the 07D Obsidian output subdir |

Each contributes a boolean AND-chained into `proof_passed`; any finding flips it `False`
(fail-closed). The report gains `scanned_modules_07d`, the seven `checks_detail` entries, an extended
`phase` string, and `no_raw_values_persisted` (now AND `guards_07d_ok` and `content_07d_ok`) +
`no_raw_values_persisted_scope` / `note` covering the 07D surfaces. **Findings are pattern labels and
`table.column` / file locations only — never the offending value.** Prompt 13 added no new command
(the objective was to *extend* the proof). **Phase 08A Prompt 01** later added a thin read-only CLI
alias `construction-agent data-quality phase-07d-no-writeback-proof` that delegates to the same
`build_data_quality_no_writeback_proof` builder, so the matrix's `phase-07d-no-writeback-proof`
command name now resolves to an implemented surface (the alias payload adds `alias_of`; the report is
byte-identical to `no-writeback-proof`).

### Constants

- `_PHASE_07D_MODULES` (9): `relationships/cross_source_substrate.py`, `relationships/contracts.py`,
  `meeting_prep/brief_builder.py`, `issue_history/issue_history_builder.py`,
  `risk_digest/risk_digest_builder.py`, `aging_exposure/aging_exposure_builder.py`,
  `correspondence/correspondence_context.py`, `obsidian/cross_source.py`, `data_quality/phase_07d.py`.
- `_PHASE_07D_TABLE_GUARDS` (10 tables × 8 guard columns), `_PHASE_07D_TABLES`,
  `_PHASE_07D_EVIDENCE_SUBDIR`, `_PHASE_07D_OBSIDIAN_BASE`.

### Why a clean 07D pass is meaningful

The scanners are not vacuous: a synthetic module with `import requests` + `client.post(...)` is
flagged (tested), and injecting a `?sig=…` tokenized URL into a V25 safe text column fails the content
scan closed (tested, value never echoed). The nine 07D modules carry no mutation verb / dangerous
import; the secret patterns are value-shaped, so the 07D evidence files (which quote the `_LEAK`
documentation literal `Bearer |eyJ|-----BEGIN|https?://`) scan clean; the live V25 tables have 0 guard
violations and 0 content findings.

## Guardrails

Local-first, read-only, offline; no live call. Fail-closed: the command exits non-zero (3) when the
proof fails. Findings never echo the offending value. Out-of-scope (disclosed, unchanged): the Phase
06A raw file-intelligence staging layer.

## Validation

ruff / `mypy src` (190 files) / compileall clean; pytest **+5 new 07D tests**; the existing
07A/07B/07C proof tests pass (one 07A scope-string assertion broadened to substring checks for the
four phases). Live `data-quality no-writeback-proof` `proof_passed=true` now covering 07D (9 modules,
10 V25 tables, evidence, Obsidian).

## Files

- `src/hb_assistant/construction/data_quality/safety.py` (07D constants + arm).
- `tests/test_phase07d_no_writeback_proof.py` (new); `tests/test_data_quality_safety_proof.py`
  (scope assertion broadened).
- **08A Prompt 01:** `src/hb_assistant/cli/construction.py` (`phase-07d-no-writeback-proof` alias
  command) + `tests/test_construction_cli_commands.py` (alias CliRunner test).

See `docs/evidence/construction-intelligence-phase-07d-cross-source-meeting-prep/13-no-writeback-no-secret-no-raw-content-proof.md`.
