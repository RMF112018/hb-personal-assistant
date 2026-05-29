# Phase 05 Prompt 11 — Financial Query Commands & Obsidian Register

> **Scope:** local-only `procore live financial` query commands + a
> `procore obsidian financial` marker-bounded register over the V8/V9 tables, signals,
> and history. **No network / token / live gate.** Last build prompt before closeout.

## 1. Query commands — `hb-assistant procore live financial <verb>`

New sub-group under `procore live` (`cli/procore.py`). Each runs
`SQLiteMigrator().apply()` then reads SQLite, emitting a JSON envelope via `_emit`
(`{command, ok, phase:"Phase 05 Prompt 11", project_key, filters, <rows>, guardrails}`;
`guardrails.live_calls_disabled = true`).

| Command | Backend | Filters |
|---|---|---|
| `summary` | `read_financial_contract_summary` + per-family/family counts + open signal count | — |
| `contracts` | `read_financial_contract_summary` | `--type prime\|commitment\|purchase_order` |
| `changes` | `time_window.parse_since` → `get_procore_changes`, filtered to financial endpoints | `--since` (relative/ISO) |
| `invoices` | `read_financial_subcontractor_invoices` | `--status` |
| `budget` | `read_financial_budget_rows` (+ `read_financial_budget_changes`) | `--view-id` (→ budget_view_key) |
| `risk` | `read_financial_risk_view` | — |
| `coverage` | offline normalizer-diff (`--raw-payload` file) | `--endpoint`, `--raw-payload` |

**Coverage semantics:** load the raw payload JSON (first record), run
`resolve_normalizer(endpoint)` on it, and report raw top-level **scalar** field names
not represented in the resulting `canonical_fields` (covered if a canonical key equals
the raw key or starts with `"<raw>_"`; nested dict/list keys are skipped). Output:
`raw_scalar_field_count`, `captured_field_count`, `omitted_field_count`,
`omitted_fields`. Detects fields the projection drops (e.g. an unrecognized amount
column) — tested: a planted `mystery_amount` is flagged; `estimated_amount` is not.

## 2. Read views (additive) — `store/procore_financials.py`

`read_financial_change_orders(project_key, change_order_family=None)`,
`read_financial_payment_applications(project_key, status=None)`,
`read_financial_compliance_documents(project_key, status=None)` — mirror the existing
read-view pattern (`_open`/`_rows`, dynamic WHERE, `record_key` in SELECT). Feed the
register sections that previously had no read view. No `_COLUMNS`/upsert/redaction changes.

## 3. Obsidian register — `procore obsidian financial` + `procore/financial_register.py`

`build_financial_register` / `apply_financial_register` mirror the existing
`obsidian_register.py` enriched-register pattern (reusing `_table`/`_section` and
`obsidian._write_procore_artifact` with marker kind `FINANCIAL-REGISTER`). The CLI
command mirrors `obsidian enriched` (`--project`, `--dry-run` default, `--apply`,
`--confirm`, `--json`; TTY/confirm gate on apply).

- **Note:** `01_Projects/<project>.procore-financial-register.md`, marker-bounded
  `<!-- HB-PROCORE-FINANCIAL-REGISTER:START/END -->` (dynamic-fallback marker; the
  existing summary-only `financial_snapshot` is untouched).
- **10 sections:** Contract Summary · Open Financial Actions · Prime Change Orders ·
  Commitments and Compliance · Subcontractor Invoices · Payment Applications · RFQs and
  Change Events · Budget Movement · Retainage / Payment Risk · Last 30-Day Financial Changes.
- **Source-linked:** every populated table row's first column is its `record_key`
  (markdown-escaped pipes), and every section header carries a
  `_Query: \`hb-assistant procore live financial …\`_` local query reference.
- **Redaction:** rows are built only from already-redacted read-view columns (record_key,
  ids, numbers, status, amounts, dates, `*_redacted`) — no titles/descriptions/URLs are
  selected — and a defensive `_assert_no_raw` output fence (URL/email/Bearer/PEM/`sig=`)
  fails closed before any write.
- **Dry-run vs apply:** dry-run renders only (`written_paths == []`, no `01_Projects/`
  dir created); `--apply --confirm` writes one note. Re-apply is **byte-identical**
  (idempotent marker replace).

## 4. Tests

- `tests/test_procore_financial_cli.py` (14): `--help` exits 0 for the group + all 7
  verbs + `obsidian financial`; JSON-shape over a seeded temp DB (projected via the
  family dispatchers; reads pointed at the temp DB by patching `get_connection` across
  `connection`/`migrator`/`procore_financials`/`procore_enrichment`/`procore_history`);
  filter coverage (`contracts --type`, `invoices --status`, `budget`, `changes --since`,
  `risk`); `coverage` flags an omitted amount field and not a captured one;
  `guardrails.live_calls_disabled` asserted.
- `tests/test_procore_financial_register.py` (4): 10 sections + every row carries its
  `record_key` + a query reference; no raw URL/email/Bearer/PEM/`sig=`; apply writes one
  marker-bounded file under `01_Projects/` (temp vault via `HB_CONSTRUCTION_VAULT_ROOT`)
  and re-apply is byte-identical; build (dry-run) writes no file.

## 5. Verification run

- `ruff check .` clean; `ruff format` clean on edited source; `mypy src` → no issues in 115 source files.
- `pytest -m "not integration and not live and not manual"` → **1239 passed, 1 skipped, 1 deselected** (was 1221; +18 new tests).
- End-to-end local: `procore live financial summary --project tropical --json` →
  `ok=true`, `live_calls_disabled=true`; `procore obsidian financial --project tropical
  --dry-run --json` → 10 sections, `written_paths=[]`; endpoint posture unchanged (59/27/32).

## 6. Acceptance criteria status

| Criterion | Status |
|---|---|
| Financial query commands are local-only and tested | ✅ 7 verbs under `procore live financial`, no network/token/live gate; help + JSON-shape + filter + coverage tests |
| Obsidian financial register renders useful source-linked sections | ✅ 10 sections; every row has `record_key`; every section has a local query reference; marker-bounded + idempotent |
| No raw sensitive data emitted | ✅ redacted read-view columns only + `_assert_no_raw` output fence; no-raw test scan |
