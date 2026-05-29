# Phase 05 Prompt 03 — Shared Financial Normalizers & Redaction Utilities

> **Scope:** the shared toolkit for financial normalization + redaction. Two new modules; no
> per-endpoint normalizers, no live calls, no schema/migration, no writeback. Companion:
> [`02-v8-financial-schema-and-repository-model.md`](./02-v8-financial-schema-and-repository-model.md).

## 1. New modules

### `src/hb_assistant/procore/normalizers/financial.py` (pure — no DB)

One import for per-endpoint normalizers. Reuses (does not duplicate) `normalizers/hashing.py`
and `normalizers/entities.py`, and adds the financial-specific utilities:

| Utility | Behavior |
|---|---|
| `parse_amount(value)` | Decimal-safe → `str`. Source strings preserved verbatim (trimmed; trailing zeros + sign intact); `int`→`str`; `float`→shortest round-trip repr; `bool`/`None`/non-numeric→`None`. **No float/Decimal re-coercion that drops precision.** |
| `extract_currency_config(raw)` | `currency_iso_code`, `base_currency_iso_code`, `currency_exchange_rate` (rate via `parse_amount`); handles nested `currency_configuration` + top-level; None-omitted. |
| `extract_wbs_cost_code(obj)` | `wbs_code_id`/`wbs_flat_code`/`wbs_description` + `cost_code_id`/`line_item_type_id`/`tax_code_id` (business labels preserved). |
| `mask_excerpt(text, max=200)` | Masks `[email]`/`[phone]`/`[url]`, collapses whitespace, truncates. |
| `html_to_text(value)` | Strips HTML tags + unescapes entities + collapses whitespace. |
| `summarize_text(value, max=120)` | HTML→text then `{type, length, hash_prefix, excerpt}` (excerpt PII-masked). Raw HTML/text never returned. |
| `attachment_path(url)` | Path-only (drops scheme/host/query → signed-URL tokens never persist). |
| `custom_field_policy(cf)` | Phase 04B policy (decimal/boolean/lov preserved; strings hashed) — reuses `entities.custom_field_entities`. |
| `build_amount_facts(canonical, *, amount_columns, source_table)` | Generic value-level emitter → `{amount_name, amount_value, source_field_path}` per present amount (value via `parse_amount`); None skipped. |

Re-exposed shared primitives: `person_hash_summary`, `hash_identifier`, `hash_summary`
(person PII → hash), `company_entity` / `company_entity_from_name` (org labels preserved),
`attachment_entities` (path-only), `custom_field_entities`, `redact_url_to_path`.

### `src/hb_assistant/store/procore_financial_projection.py` (store layer)

The **shared** projection primitives (per-endpoint `project_*` are Prompts 04–09). Self-contained
store module (no `hb_assistant.procore` import), imports `.procore_financials` + `.procore_enrichment`:

- `emit_amount_facts(*, project_key, record_key, endpoint_id, facts, created_at_utc,
  currency_iso_code=None, base_currency_iso_code=None, db_path=None) -> list[str]` — the generic
  amount-fact emitter; loops `procore_financials.emit_financial_amount_fact` (deterministic id →
  idempotent; amount stored verbatim TEXT). Skips facts with no value/name.
- `link_record_entities(*, project_key, record_key, endpoint_id, people=None, companies=None,
  now_utc, db_path=None) -> dict` — hashes people via `extract_people_refs` (PII never stored),
  preserves company/vendor labels via `extract_company_refs`, and emits relationship edges via
  `emit_record_edge`. No new tables.

## 2. Posture / safety

- **Money + quantities + rates** preserved as decimal-safe strings → usable for aggregation and
  comparison. **Currency config, WBS/cost-code ids + labels** kept as structural business facts.
- **Person PII** hashed; **company/vendor/trade labels** kept as org metadata. **Free text / HTML**
  reduced to hash+length+masked-excerpt — raw never persists. **Attachment URLs** path-only —
  signed-URL query strings stripped.
- No live GET/writeback; no schema/migration change; reuses existing hashing/entities/enrichment
  helpers (no duplicated logic).

## 3. Tests

- `tests/test_procore_financial_normalizers.py` (9): negative + high-precision decimal strings
  preserved byte-for-byte (incl. trailing zeros, trimming); int/float/None/bool handled; currency
  config (nested + top-level); WBS/cost-code extraction; `mask_excerpt` masks email/phone/url;
  `summarize_text` strips HTML + no raw text/email persists + hash present; `attachment_path`
  strips a signed-URL query (`?sig=…&token=…&company_id=…` → `/prostore/abc.pdf`); company label
  preserved + person PII hashed; custom-field decimal preserved / string hashed; `build_amount_facts`
  skips absent + preserves decimal.
- `tests/test_procore_financial_projection.py` (2): `emit_amount_facts` persists to
  `procore_financial_amount_facts` (idempotent — re-emit yields no duplicates, decimal byte-exact,
  currency carried, `raw_body_persisted=0`); `link_record_entities` → person hashed (no raw PII in
  `procore_people_entities`), company label preserved in `procore_company_entities`, edges in
  `procore_record_edges`.

## 4. Verification run

- `ruff check .` clean (`financial.py` is in ruff scope; `store/` excluded). `mypy src` → no issues
  in 109 source files. `pytest -m "not integration and not live and not manual"` → **1141 passed,
  1 skipped, 1 deselected** (was 1130; +11 new tests).

## 5. Acceptance criteria status

| Criterion | Status |
|---|---|
| Shared utilities exist and are covered by tests | ✅ both modules + 11 tests |
| Raw text, contact PII, and signed URLs do not persist | ✅ `summarize_text`/`mask_excerpt`/`attachment_path` + person-hash tests |
| Financial values remain usable for aggregation/comparison | ✅ decimal-safe `parse_amount` + `build_amount_facts` + `emit_amount_facts` round-trip tests |
