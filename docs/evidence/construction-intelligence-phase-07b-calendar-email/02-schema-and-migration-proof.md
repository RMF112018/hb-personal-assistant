# Schema And Migration Proof — Phase 07B Prompt 02

**Date:** 2026-05-31
**Phase:** 07B — Calendar & Email Thread Intelligence
**Prompt:** 02 — Calendar Schema And Source Registry
**Baseline (pre-Prompt 02):** HEAD `ee44b39` (`main`), package `1.3.0`, schema **V22**.
**Result:** additive schema **V23** + full policy/contract foundation; baseline stays green.

All commands under `source .venv/bin/activate`. Additive/local only — no external mutation, no
`--apply`-less write path, no raw/private values. **Version note:** the prompt text says "V22
schema," but V22 was consumed by Prompt 01 (`v22_mart_raw_body_guardrail`); this migration is **V23**.

## 1. What changed

- **V23 migration** (`store/migrator.py`, `v23_calendar_email_thread_intelligence`,
  `LATEST_SCHEMA_VERSION = 23`): 8 additive tables + 6 indexes, all `CREATE … IF NOT EXISTS`; V1–V22
  untouched. Tables: `calendar_source_locations` (CHECK `read_only = 1`), `calendar_sync_state`,
  `calendar_crawl_runs`, `calendar_event_index`, `calendar_event_attendees`,
  `calendar_project_match_candidates`, `meeting_email_relationship_candidates`,
  `email_thread_summary_materialization_runs`. Every event/candidate/run table carries the standard
  `CHECK(<flag> = 0)` guardrails (raw_body / full_text / raw_prompt / raw_response /
  external_writeback as applicable). Identifying values are hashed/redacted only.
- **Policy seeds** (`resources/config/`): `calendar_source_policy.seed.yaml`,
  `email_thread_summary_policy.seed.yaml`, `review_required_calendar_email_rules.seed.yaml`.
- **JSON contracts** (`src/hb_assistant/resources/json/`): `calendar_project_match_contract.json`,
  `email_thread_summary_contract.json`, `meeting_email_relationship_candidate_contract.json`.
- **Loaders** (`construction/calendar/{__init__,policy,contracts}.py`): Pydantic policy models that
  enforce safety invariants at load (read-only; no event-body/join-URL/decrypted-body/raw-prompt/
  raw-response persistence) + JSON contract loaders that assert auto-promotion disabled.
- **Repository helpers** (`construction/store/repositories.py`): `upsert_calendar_source_location`
  (rejects non-read-only sources), `upsert_calendar_sync_state`.
- **Lifecycle contract** (`table_lifecycle_status_contract.json`): +8 tables so
  `data-quality table-inventory` classifies them.

## 2. Migration proof (temp DB)

```bash
# apply twice -> idempotent, head stable at 23
SQLiteMigrator(db).apply() == 23  ; SQLiteMigrator(db).apply() == 23
```
- 8 new tables present; 6 new indexes present; exactly one `schema_migrations` row for v23.
- V1/V20/V21/V22 rows intact; V20/V22 `CHECK(raw_body_persisted=0)` preserved; legacy
  `calendar_events` (V1) unchanged (no `project_key` added).
- CHECKs enforced: `read_only = 0` rejected on `calendar_source_locations`; `raw_body_persisted = 1`
  and `raw_prompt_persisted = 1` rejected; UNIQUE(source_id, graph_event_id_hash) enforced.
(Covered by `tests/test_phase_07b_schema_v23.py`.)

## 3. Policy / contract / registry proof

`tests/test_phase_07b_calendar_policy.py`: all 3 YAML policies + 3 JSON contracts load and validate;
policy validators reject unsafe values (`read_only=False`, `persist_event_body=True`,
`persist_raw_prompt=True`); `upsert_calendar_source_location` round-trips and its read-only guard
raises on a writeback attempt.

## 4. Validation matrix (actual exit codes)

| Command | Exit | Note |
|---|---|---|
| `python -m compileall src tests` | **0** | |
| `ruff check .` | **0** | |
| `mypy src` | **0** | 156 source files |
| `pytest -m "not live and not integration and not manual"` | **0** | 0 failed / 1902 collected (8 xfail unchanged) |
| `construction-agent validate --json` | **0** | `schema_version=23`; `6 projects, 14 sources` (registry unchanged) |
| `procore validate --json` | **0** | |
| `graph files status --json` | **0** | |
| `graph mail status --json` | **0** | |
| `graph calendar status --json` | **2** | still `No such command` — Prompt 03 scope |
| `data-quality gates --json` | **0** | |
| `data-quality no-writeback-proof --json` | **0** | 07A-scoped; unaffected by V23 |
| `data-quality table-inventory --json` | **0** | now classifies the 8 new tables from the contract |

`table-inventory` classification of the new tables (all `source: contract`, `phase_owner: 07B`):
registry/state/receipts → `operational_empty_expected`; event-index/attendees/candidates →
`operational_empty_blocking` (blocking_for_phase 07D).

## 5. Guardrail attestation

- No M365/Procore/SharePoint/OneDrive/Outlook/calendar mutation or writeback; no live external call.
- V23 is a local additive schema applied by the migrator; new helper writes only local SQLite and
  refuses non-read-only sources; no new `--apply`-less write path.
- No raw email/calendar body, prompt, response, token, secret, PEM, signed/download URL, raw delta
  link, or private value in schema, seeds (placeholders only, e.g. `mailbox_owner: current_user_hash_only`),
  contracts, code, tests, or this evidence. Redaction scan of new artifacts: clean.
- No Phase 07D meeting-prep readiness claimed; 07D remains blocked.

## 6. Go / No-Go for Prompt 03

**GO — Prompt 03 (Read-only Graph Calendar Status And Guardrails) may proceed.** The additive V23
schema + source registry + policy/contract foundation are in place and green; `graph calendar
status` (exit 2) is the explicit subject of Prompt 03.

**Prompt 02 complete.**
