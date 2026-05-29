# Phase 05 Prompt 02 — V8 Financial Schema & Repository Model

> **Scope:** additive **V8** SQLite migration + a standalone financial repository module.
> No live calls, no live-sync wiring (Prompt 10), no writeback. Amounts preserved as
> decimal-safe TEXT; redaction guards enforced. Companion artifacts:
> [`00-…source-inventory.md`](./00-repo-truth-rebaseline-and-financial-endpoint-source-inventory.md) ·
> [`01-endpoint-registry-and-live-gate-shell.md`](./01-endpoint-registry-and-live-gate-shell.md)

## 1. Migration (V8)

`src/hb_assistant/store/migrator.py` gains a `V8_STATEMENTS` list + a version-gated `apply()`
block (`INSERT … (8, 'v8_procore_financials', …)`). `SQLiteMigrator().apply()` now returns
**8**. All DDL is `CREATE TABLE/INDEX IF NOT EXISTS` (idempotent); V1–V7 lists are untouched.

**13 tables** (10 verbatim from `resources/sql/phase_05_financial_schema_additions.sql` + 3
HB-authored extensions), **7 indexes**:

| # | Table | Source | PK |
|---|---|---|---|
| 1 | `procore_financial_contracts` | package SQL | `record_key` |
| 2 | `procore_financial_line_items` (generic via `line_item_kind`) | package SQL | `line_item_key` |
| 3 | `procore_financial_change_orders` | package SQL | `record_key` |
| 4 | `procore_financial_payment_applications` | package SQL | `record_key` |
| 5 | `procore_financial_invoice_items` | package SQL | `invoice_item_key` |
| 6 | `procore_financial_rfqs` | package SQL | `record_key` |
| 7 | `procore_financial_change_events` | package SQL | `record_key` |
| 8 | `procore_financial_budget_views` | package SQL | `budget_view_key` |
| 9 | `procore_financial_budget_rows` | package SQL | `budget_row_key` |
| 10 | `procore_financial_amount_facts` | package SQL | `amount_fact_id` |
| 11 | `procore_financial_change_order_line_items` | **HB extension** | `line_item_key` |
| 12 | `procore_financial_budget_changes` | **HB extension** | `budget_change_key` |
| 13 | `procore_financial_compliance_documents` | **HB extension** | `compliance_key` |

The 3 extension tables (per the approved scope decision) cover families named in the ledger
prose but **absent from the authoritative SQL**. They are modeled on the verbatim schema
conventions (TEXT amounts, both redaction CHECK columns, parent `*_record_key`) and are
**provisional** — columns to be reconciled against live payloads at promotion. They are
flagged as extensions in the migration comments.

### Redaction guards (table-level)

Every table carries `raw_body_persisted INTEGER NOT NULL DEFAULT 0 CHECK(raw_body_persisted = 0)`;
all except `procore_financial_amount_facts` also carry
`redaction_applied INTEGER NOT NULL DEFAULT 1 CHECK(redaction_applied = 1)` (matching the
package SQL, where `amount_facts` omits the latter).

## 2. Repository — `src/hb_assistant/store/procore_financials.py`

Standalone module (no `hb_assistant.procore` import — store-layer independence, mirroring
`procore_history.py`). House style: free functions, keyword-only args, `get_connection` +
`transaction`, parameterized `INSERT … ON CONFLICT(pk) DO UPDATE SET …` via a DRY internal
`_persist(table, pk, row)` that whitelists columns (unknown → `ValueError`, fail-closed) and
always sets the redaction guards.

**Upserts** (one per table): `upsert_financial_contract`, `upsert_financial_line_item`
(contract/commitment/PO via `line_item_kind`), `upsert_financial_change_order`,
`upsert_financial_change_order_line_item`, `upsert_financial_payment_application`,
`upsert_financial_invoice_item`, `upsert_financial_rfq`, `upsert_financial_change_event`,
`upsert_financial_budget_view`, `upsert_financial_budget_row`, `upsert_financial_budget_change`,
`upsert_financial_compliance_document`. **`emit_financial_amount_fact`** computes a
deterministic `amount_fact_id` (hash of project/record/amount_name/period/wbs) → re-emission
is a no-op. **Reads:** `read_financial_contract_summary`, `read_financial_amount_facts`,
`read_financial_risk_view` (derived: unexecuted contracts, executed-but-unpaid change orders;
`ORDER BY` for determinism).

### Decimal preservation (acceptance-critical)

Amount params are `Optional[str]` and stored **verbatim** in TEXT columns; the module never
calls `float()` (TEXT affinity would re-format a float and silently lose precision). Test
`test_decimal_amount_strings_survive_unchanged` persists `-1234567.89012345`,
`0.000000000001`, `999999999999.99`, `0.10`, `-0.30` and reads each back byte-for-byte (and
asserts the stored value is a `str`).

### Redaction at the repository boundary (defense-in-depth)

`_redact_field` enforces redaction regardless of caller: `title_redacted` / `name_redacted` /
`wbs_description_redacted` / `notes_summary_redacted` → `_redact_excerpt` (masks
`[email]`/`[phone]`/`[url]`, truncates); `description_summary_json` → `{hash, len, excerpt}`
JSON (no raw body); `attachment_path_redacted` → URL path only (drops signed-URL query). Test
`test_title_is_redacted_at_repository_boundary` proves an email/phone in a title is masked.

**No live-sync wiring** here — the dispatch invoking these functions is Prompt 10.

## 3. Tests

- `tests/test_procore_financials_v8.py` (7): V8 applies from empty DB (`apply()==8`, all 13
  tables + 7 indexes); V1/V6/V7 representative tables intact; idempotent re-apply (`==8`,
  `schema_migrations` v8 count==1); CHECK rejects `raw_body_persisted=1`, `redaction_applied=0`,
  and the amount-facts raw-body CHECK.
- `tests/test_procore_financials_repository.py` (5): contract upsert idempotent + PK dedup;
  **decimal strings survive unchanged**; amount-fact emission idempotent + decimal preserved;
  title redacted at boundary; read views deterministic.
- Updated pre-existing version assertions 7 → 8 in `tests/test_procore_history_migration_v7.py`
  (4) and `tests/test_construction_store_repositories.py` (3) — intentional schema advance; the
  tests' semantic intent (V7 tables exist, idempotent, earlier migrations intact) is preserved.

## 4. Scope / posture notes

- `store/` is outside the ruff + mypy strict scope (`extend-exclude` / mypy `exclude` regex),
  consistent with `procore_history.py`/`procore_enrichment.py` — **no pyproject change**; the
  module is still fully annotated. `ruff check .` and `mypy src` stay clean.
- Migrations additive + idempotent; no V1–V7 table altered. No live GET/writeback. No raw
  payload bodies, secrets, tokens, or signed URLs persisted/logged. Amounts as TEXT, no float
  coercion.

## 5. Verification run

- `ruff check .` clean; `mypy src` → no issues in 108 source files.
- `pytest -m "not integration and not live and not manual"` → **1130 passed, 1 skipped,
  1 deselected** (was 1119; +11 new financial tests).
- `SQLiteMigrator().apply()` on a tempfile → 8; re-apply → 8 (idempotent).

## 6. Acceptance criteria status

| Criterion | Status |
|---|---|
| `SQLiteMigrator().apply()` reaches the new version | ✅ returns **8** |
| All financial tables/indexes exist | ✅ 13 tables + 7 indexes (test-verified) |
| Re-applying migration is a no-op | ✅ `==8` twice; v8 row count == 1 |
| Repository upserts deterministic and idempotent | ✅ PK conflict-upsert; deterministic amount-fact id |
| No binary-float corruption of amount strings | ✅ decimal round-trip test (5 high-precision/negative values) |
| V1–V7 tables remain intact | ✅ test asserts V1/V6/V7 tables present at V8 |
