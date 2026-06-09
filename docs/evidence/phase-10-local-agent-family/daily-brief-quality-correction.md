# Phase 10 Daily Brief Quality Correction — validation evidence (redacted)

Date: 2026-06-09. Branch: `main`. Validation run against a **copy** of the working DB (the `(Dev)`
app-support root), into temp output dirs — no real vault / app-support / external system touched.
All values below are redacted (no raw subjects, paths, prompts, or model responses).

## Model benchmark (synthesis profile)

Same prebuilt context packet, 2 trials per profile, real Ollama (local):

| Profile | Model | Schema-valid | Attempts | Avg latency | Verdict |
|---|---|---|---|---|---|
| `default_extract` | mistral-nemo:12b | 2/2 | 1, 1 | ~38 s | reliable, fast |
| `review_filter` | qwen2.5:14b | 1/2 direct (1 fell back to nemo) | 1 / 2(fb) | ~83 s | less reliable, slower |

**Pinned: `mistral-nemo:12b`** for the `brief_synthesis` profile (fallback `default_extract`).
Note: an earlier arm with `extra="forbid"` + no JSON skeleton in the prompt produced
`schema_invalid` after 3 attempts → **correctly degraded** (fail-closed proof). Switching nested
schema to `extra="ignore"` (unknown fields dropped, never persisted) + adding a JSON shape skeleton
made mistral-nemo reliable (2/2, 1 attempt).

## Live apply validation (status=success)

- `status=success`, `synthesis.status=ok`, `schema_valid=true`, `attempts=1`, `degraded=false`,
  `egress_scan.clean=true`, model `mistral-nemo:12b`.
- Routing: brief written to the governed `Work/Daily Brief` folder (temp dir in validation); the
  legacy Phase 08A folder is guarded (a run pointed at it fails closed → `vault_brief_dir_refused`).
- Date window: Tuesday → `standard_weekday` (lookback prev business day → lookahead next business day).
- Brief sections present: Executive Summary; What Changed Since Last Brief; Critical / Due Today;
  Open Commitments & Follow-Ups (empty-state when none); Today's Meetings (local times + project +
  why + prep + next action); Project / Procore Signals; Recommended Next Actions; FYI; Needs Review /
  Data Gaps; + collapsed Source-Linked Candidates (audit) appendix.
- Calendar quality: PTO / lunch / placeholder events demoted/excluded from Today's Meetings; prep-
  worthy meetings (OAC, RFI/Submittal review, 3-week update) promoted with prep notes.
- Project inference: known tokens resolved to canonical HB keys (e.g. `tropical`,
  `pga-modern-garage`); unresolved items grouped under "Needs Project Review" (no inline
  `project:__unassigned__` in the body).
- Technical relationship rows (`… ↔ …raw_content`) absent from the body (folded / appendix-only).

## Raw-content boundary proof (live)

| Surface | Raw subject present? | Expected |
|---|---|---|
| Obsidian note | yes | ✓ raw allowed (private) |
| Browser HTML | yes | ✓ raw allowed (private) |
| Status JSON (`latest-status.json`) | **no** | ✓ redacted |
| Persisted `daily_brief_action_candidates.title_redacted` | redacted hash | ✓ |
| `local_model_run_receipts` | hash-only (status/schema_valid/hashes) | ✓ no raw prompt/response |
| Guard columns (13) | sum = 0 | ✓ |
| `egress_scan.clean` | true | ✓ (no URLs/join/email/token) |

## Degraded / fail-closed proof

- Model unavailable/timeout/schema-invalid/empty → `synthesis_degraded=true`, run downgraded to
  `partial`, a clearly-marked **DEGRADED** brief written to `daily-brief-latest-attempted.html`, the
  last successful brief + pointer **preserved** (not advanced). Verified by unit tests
  (`test_26_27_degraded_preserves_last_good_and_is_marked`) and the live `extra="forbid"` arm.

## Tests

`tests/test_phase_10_daily_brief_correction.py` — 27 tests covering the 30 required scenarios
(routing, synthesis fail-closed, content quality, alias inference, calendar noise, raw-boundary,
degraded preservation, egress, diagnostics). Phase 10 regression suites remain green.
