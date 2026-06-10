# Priority 1 — Calendar Project/Category Resolution (Prompt 01)

## What changed

- **New** `src/hb_assistant/construction/second_brain/local_ai/calendar_category.py`:
  `resolve_calendar_category(...) -> CalendarResolution(project_key, category, confidence,
  matched_alias, needs_review, reason)`. Categories: `project`, `internal_company`,
  `internal_training`, `internal_time_off`, `needs_review`, `unknown`.
- **Refinement 1 honored:** the project arm **delegates** to the canonical alias matcher. Added
  `resolve_project_alias()` to `project_aliases.py` as the single matching implementation and made
  the existing `resolve_project()` a thin wrapper over it — no forked semantics, no duplicated
  alias logic. The category module only adds internal/PTO/training/needs-review classification
  *around* that one matcher (plus `candidate_tokens` reuse for the review-safe fallback).
- **Wired into** `calendar_prep.py`: replaced the bare `__unassigned__` fallback with the resolver;
  persists the real project key for `project` and review-safe sentinels otherwise; the persisted
  candidate `confidence` now reflects resolution confidence; added `category`/`needs_review`/
  `matched_alias` to each event view and `category_distribution` / `needs_review_count` to the
  summary rollups. Unresolved-token diagnostics now key off category (needs_review/unknown), not a
  raw sentinel string.

## Repo-truth alias mapping (Refinement 2)

`TWN → tropical`, `Wellington → the-wellington`, `Alton Hilltop/Hilltop → alton-hilltop-pbg`,
`PGA → pga-modern-garage` are treated as **repo truth** because they already exist in
`resources/config/project_aliases.seed.yaml`. No new guessed mappings were added.

## Safe demonstration over the audit's observed subjects

| subject (redacted-equivalent) | category | project_key | needs_review |
|---|---|---|---|
| Pre-Submission Bid Review - The Wellington Homes | project | the-wellington | False |
| TWN OAC | project | tropical | False |
| TWN Weekly RFI/Submittal Review | project | tropical | False |
| FW: Alton Hilltop Bi-Weekly | project | alton-hilltop-pbg | False |
| [DUE TODAY] Project Financial Forecasts | internal_company | __internal_company__ | False |
| Andrew PTO | internal_time_off | __internal_time_off__ | False |
| LMA Training: …Session #5… | internal_training | __internal_training__ | False |
| TWN Weekly LUNCH & Team Meeting | project | tropical | False |

Project-like meetings no longer all land as `__unassigned__`; internals are categorized separately;
low-confidence project-looking text routes to `__needs_review__` (review-safe, never invented).

## Tests

- `tests/test_phase_10_calendar_category.py` — 11 passed (exact alias, case-insensitive, longest-alias
  delegation, PTO/training/company internals, ambiguous→needs_review, unknown, project-wins-over-internal,
  indexed-key short-circuit, redacted-input-only).
- `tests/test_phase_10_calendar_meeting_prep.py` — 24 passed (no regression).
- `ruff check` on changed files: clean.

Full DB-copy proof of nonzero resolved calendar candidates is in `06-db-copy-live-proof/`.
