# Phase 04B Prompt 04 — Inspection / Section / Item Enrichment

**Date:** 2026-05-29 · **Module:** `src/hb_assistant/store/procore_inspection_projection.py` ·
**Wiring:** `src/hb_assistant/procore/live_sync.py`.

## Summary

Projects the `inspections` / `inspection-sections` / `inspection-items` payloads into the six V7
inspection tables, derives second-brain meaning, and emits the required action signals + relationship
edges. Wired into the live-sync flow for the three inspection endpoints (after the latest-state upsert
and Prompt-02 history recording, in its own guard). Reads the **raw** payload (the item normalizer
drops `evidence_configuration`); only structural ids / labels / flags persist — no raw-body blob.

## Projections (tables populated)

| function | tables |
|---|---|
| `project_inspection_record` | `procore_inspection_records` |
| `project_inspection_section` | `procore_inspection_sections` |
| `project_inspection_item` | `procore_inspection_items`, `procore_inspection_response_sets`, `procore_inspection_response_options`, `procore_inspection_evidence_rules` |

## Derived meaning

- **Safety detection** — `is_safety` from `inspection_type.name` (fragments: safety/incident/injury/
  near-miss/osha/ppe/fall).
- **Open/closed** — closed if `closed_at` set or status contains "clos"; else open.
- **Overdue** — `overdue` flag.
- **Counts** — item/respondable/inspected/conforming/deficient/observations counts persisted verbatim.
- **Response interpretation** — `responded_with` matched against `response_set.responses[]`; the chosen
  option's `status` → `is_conforming` (conforming), `is_deficient` (deficient), `is_not_applicable`
  (not_applicable); `is_unanswered` for "No Response"/empty/no-category. `response_status` records the
  category (or `no_response`).
- **Section risk category** — keyword map on section name → high (highest/high/fall/critical/safety/
  hazard), medium, low, general.
- **Evidence rules** — from `evidence_configuration.{observation,photo}.{response_option_ids,status_ids}`
  + `item_reference_ids`; `requires_observation`/`requires_photo` = bool of the id lists.

## Edges & action signals

Edges (`procore_record_edges`): inspection→inspector, inspection→created_by,
inspection→responsible_contractor, inspection→at_location, inspection→trade, inspection→item
(`has_item`), section→item (`section_has_item`), item→response_set (`uses_response_set`).

Action signals (`procore_action_signals`): `inspection_open_safety`, `inspection_overdue`,
`inspection_has_deficient_items`, `inspection_has_unanswered_items`, `inspection_item_unanswered`,
`inspection_item_failed`, `inspection_item_non_conforming`, `inspection_item_requires_photo_evidence`,
`inspection_item_requires_observation`.

History (reused from Prompt 02's diff): `inspection_item_response_changed` /
`inspection_item_became_unanswered` / `inspection_item_became_deficient` fire when the normalized
inspection-item record's `responded_with` / flags change across syncs.

## Acceptance-sample derivation (verified)

For the uploaded "Jobsite Safety Checklist" sample the projection derives:
- inspection record: name "Jobsite Safety Checklist", `is_safety=1`, status **Open**, `private=1`,
  `respondable_item_count=32`, `inspected_item_count=0`; signals `inspection_open_safety`,
  `inspection_has_deficient_items`, `inspection_has_unanswered_items`.
- section "Areas of Highest Risk" → `risk_category=high`.
- item `1.1` "Fall Exposures", `responded_with="No Response"` against a **Pass/Fail** response set →
  `is_unanswered=1`, `response_status=no_response`; signal `inspection_item_unanswered`.
- response set (Pass/Fail) + 3 options (Pass=conforming, Fail=deficient, No Response="") + evidence
  rules (`requires_observation=1`, `requires_photo=1`).

## Guardrails

People (inspectors / created_by) hashed via `extract_people_refs` (raw logins/names never stored —
verified absent in `procore_people_entities`); org/place labels kept as labels; structural ids/flags
only; all enrichment rows `raw_body_persisted=0` where present. Deterministic keys + conflict-upsert
keep projection idempotent (re-sync adds no duplicate rows). `evidence_configuration` read from raw;
the inspection normalizer is unchanged. Projection is guarded in the orchestrator so it never breaks
latest-state or history.

## Validation

```
python -m pytest -q --no-header   # full suite green (1 pre-existing skip)
ruff check .                      # All checks passed
mypy .                            # Success: no issues found in 192 source files
python -m compileall src tests    # OK
```
