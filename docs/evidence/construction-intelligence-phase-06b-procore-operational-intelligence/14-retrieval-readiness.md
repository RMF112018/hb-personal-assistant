# Phase 06B — Prompt 14: Procore Retrieval Readiness

**Status:** COMPLETE.
**Run date:** 2026-05-31
**Parent HEAD at start:** `b758469` (`phase-06b prompt-13: obsidian operational outputs`)
**Objective:** Prepare retrieval-safe Procore facts for local assistant workflows without raw body
leakage or determination risk — a source-linked, redacted **retrieval fact manifest** surfaced as
`procore live retrieval-ready --project KEY --json`. Local SQLite only; read-only; no live access.

---

## 1. What was built

Upgraded `store/procore_operational.py::build_retrieval_readiness` (the Prompt 12 placeholder) into a
retrieval fact manifest builder, and added `--max-samples` to the existing `live retrieval-ready`
CLI verb. The Prompt 12 corpus readiness probe is **preserved** (`retrieval_ready` / `reasons` /
`corpus`); the manifest is added alongside. No new table or migration (schema stays V19).

### Fact families (redacted scalars + source link only)
| Family | Source | Attributes (no raw free text / values) |
| --- | --- | --- |
| `record` | `procore_live_records` redacted scalar columns | number, title_redacted, status, updated_at |
| `action_signal` | `get_procore_action_signals` (open) | signal_type, importance, status, due_at_utc, title_redacted |
| `timeline_event` | `get_procore_changes` (metadata only) | detected_at_utc, field_path, change_type, change_category, importance |
| `exposure` | `build_cost_exposure` + `build_schedule_exposure` items | exposure type/category, importance, due_at_utc, reason_codes |
| `amount` | `read_financial_amount_facts` | amount_name, amount_value (decimal-safe TEXT), currency_iso_code |

Each fact: `fact_type` / `source_table` / `source_key` / `endpoint_id` / `procore_record_id?` /
`attributes` / `source_link` (`source_url_redacted` or `table:key`).

### Manifest payload
`total_facts`, `by_fact_type`, `by_endpoint`, `review_required_blocked`, `blocked_by_reason`
(`review_required` / `free_text_field` / `no_source_link`), `samples` (≤ `--max-samples`),
`samples_truncated`.

---

## 2. Stop-condition / no-leak reconciliation

- **No raw free text** — `canonical_json_redacted` is never read; only the redacted scalar columns of
  `procore_live_records` become record facts.
- **No change values** — timeline facts emit metadata only; `old_value_redacted` /
  `new_value_redacted` / value hashes are deliberately excluded.
- **No inline amounts on exposure facts** — financial amounts are carried only as dedicated `amount`
  facts (decimal-safe TEXT, never float-coerced or summed).
- **Review-required blocked** — `review_required = 1` live records are counted under
  `blocked_by_reason.review_required` and never emitted (a seeded review-only record is verified
  absent from the manifest).
- **Source-linked** — every fact carries a non-empty `source_link` and `source_key` (table/key/record).
- **No determinations / writeback / migration** (schema stays V19, consistent with Prompts 06–13).

---

## 3. Proof (14-retrieval-readiness-proof.json)

Seeded an isolated temp DB across all five families — an RFI record + an `rfi_overdue` signal + a
status change event, a commitment with two amount facts (`grand_total 250000.00`, `retainage`), and a
review-flagged record. Deliberate leak markers were planted in the seeded change values
(`OLDVAL/NEWVAL-SHOULD-NOT-LEAK`) and the canonical free text (`SHOULD-NOT-LEAK`):

```
manifest: total_facts 7,
  by_fact_type { record 2, action_signal 1, timeline_event 1, exposure 1, amount 2 },
  blocked_by_reason { review_required 1, free_text_field 0, no_source_link 0 }
```

Scan results: **0** planted leak markers, **0** forbidden field names
(`canonical_json`/`old_value_redacted`/`new_value_redacted`/`body`/`description`/`notes`), **0**
secret tokens; `amount_value` are strings (`250000.00` verbatim); the review-flagged record title is
absent. See [`14-retrieval-readiness-proof.json`](./14-retrieval-readiness-proof.json).

---

## 4. Validation

| Command | Exit | Result |
| --- | --- | --- |
| `pytest tests/test_procore_retrieval_readiness.py` | 0 | 7 passed (manifest families/counts, review-required blocked, samples capped, amount strings, forbidden-field leakage, corpus preserved, CLI JSON) |
| `pytest tests/test_procore_operational_cli.py` | 0 | 13 passed (Prompt 12 retrieval-ready regression — `_patch_conn` extended with `procore_history`) |
| `pytest -m "not live" tests/test_procore*.py` | 0 | no regression |
| `ruff check src/hb_assistant/cli/procore.py tests/test_procore_retrieval_readiness.py` | 0 | All checks passed |
| `mypy src` | 0 | Success: no issues found in 144 source files |
| `hb-assistant procore validate --json` | 0 | ok, 28/28 |
| `hb-assistant procore live retrieval-ready --project tropical --json` | 0 | manifest present (3938 facts, 1061 review-required blocked) |

---

## 5. Guardrail attestations

- **No live Procore call** (`no_live_call_performed: true`); **no writeback**; **read-only**
  (no migration, no persistence).
- **No raw bodies, change values, free text, tokens, signed URLs, or PEMs** — only redacted scalar
  attributes + source-link refs. Proof JSON secret/raw-value + forbidden-field + planted-leak scanned
  (0 findings).
- **No legal/claims/financial/safety/entitlement/schedule determination** (`determinations_made:
  false`); amounts stay decimal-safe strings, never summed.
