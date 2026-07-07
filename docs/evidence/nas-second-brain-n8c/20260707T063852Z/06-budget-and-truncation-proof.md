# 06 — Budget & Truncation Proof

`ProjectionBudget` (in `intelligence_projection_models.py`) bounds every projection. All limits are clamped
to hard caps before use (`clamped()`), so an operator override can only tighten, never exceed, the caps.

## Fields & hard caps

| field | default | hard cap |
|---|---|---|
| `max_items` | 50 | `MAX_ITEMS_HARD_CAP` 500 |
| `max_chars` | 60,000 | `PACK_CHARS_HARD_CAP` 200,000 |
| `max_chars_per_item` | 4,000 | `ITEM_CHARS_HARD_CAP` 8,000 |
| `max_trusted` | None | — (cap on trusted items) |
| `max_candidates` | None | — (cap on candidate items) |
| text caps | — | title 300 / summary 500 / evidence 2000 / objective 500 |

## Enforcement order (`_build_items`)

For each ordered classified item: policy exclusion → `max_trusted` → `max_candidates` → `max_items` →
per-item evidence truncated to `max_chars_per_item` then the running `max_chars` gate. Any item not
included gets an `exclusion_reason` and `included=0`; budget drops increment `dropped_count` and set
`truncated=True`.

## Tests (green, `tests/test_intelligence_projection_builder.py`)

- `test_budget_max_items_truncates` — `max_items=1` → `included_count == 1`, `truncated is True`, and every
  dropped item carries a non-empty `exclusion_reason`.
- `test_budget_max_chars_truncates` — `max_chars=1` → `included_count == 0`, `truncated is True`, and each
  excluded item's reason is `budget_max_chars`.
- `test_budget_max_trusted_and_candidates` — accept everything, cap `max_trusted=1` → exactly one included,
  and some excluded item's reason is `budget_max_trusted`.
- `test_items_preserve_provenance_and_bounded` — evidence excerpts `<= EVIDENCE_HARD_CAP` (bounded, never a
  full payload).

Exclusion reasons are explicit (`budget_max_items` / `budget_max_chars` / `budget_max_trusted` /
`budget_max_candidates` / `rejected` / `not_required` / `superseded` / `policy_*`) so truncation is never
silent — the receipt records `dropped_count` and `truncated`.
