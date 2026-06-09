# Profile Reporting Consistency Proof

The reporting contract now distinguishes the **route-selected** profile from the
**terminal/generation** profile on both the standalone and integrated surfaces.

## Contract fields (present on both standalone `daily-brief intelligence` and daily-run `intelligence`)

`task_family`, `route_selected_profile`, `route_model_name`, `route_reason_code`,
`generation_profile_id`, `terminal_profile_id`, `profile_id` (== terminal, backwards-compatible),
`model_name`, `fallback_used`, `fallback_chain`, `models_attempted`, `schema_valid`, `status`,
`withheld_reason`, `blockers`, `warnings`.

`selected_profile` (CLI top-level) now means the **route-selected** profile — consistent with
`local-model route` — not the terminal profile.

## Live observations (`/tmp` Dev DB copy, 2026-06-09)

| Scenario | route_selected_profile | terminal_profile_id | fallback_used | warnings (route-related) |
| --- | --- | --- | --- | --- |
| Enriched (primary OK) | `brief_synthesis` | `brief_synthesis` | false | — |
| Fallback (primary schema-invalid, captured pre-coercion-fix) | `brief_synthesis` | `default_extract` | true | `fallback_profile_attempted`, `terminal_profile_differs_from_route`, `schema_invalid_after_repair`, `deterministic_fallback_preserved` |

The route is reported even when the terminal profile differs, so an operator can never again mistake a
`default_extract` fallback for the routed profile. Standalone and integrated daily-run share the exact
same adapter (`build_daily_brief_intelligence`) and therefore the same route/terminal semantics
(verified: both report `route_selected_profile=brief_synthesis`).

Unit coverage: `tests/test_daily_brief_intelligence.py::test_reporting_contract_route_vs_terminal_profile`
and `::test_reporting_contract_fallback_terminal_differs_from_route`.
