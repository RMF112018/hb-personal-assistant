# 214. Phase 10A — Related-Packet Tightening + Live-Extraction Diagnostics

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10 / 10A Local Action Intelligence (repo-truth update)

## Context

Follow-up to ADR 213 (bounded packets + relationship scoring). Before any apply-path testing on the
populated dev DB, the related-packet path and live-extraction readiness needed tightening so combined
packets only form on real evidence, budgets hold, source attribution is exact, and no-output failures
are diagnosable. All changes are confined to the modules introduced in 213.

## Decision

### 1. Blocked related packets never call the model — `raw_action_intelligence.extract_actions_for_packet`
A `related_context_action_packet` with `compiled=false` short-circuits before any model call and
returns `extracted=false, blocked=true, persisted=0` plus the packet `note` and `best_confidence`.

### 2. Related-packet budget enforcement — `packet_builders.build_related_context_action_packet`
Counterparts are iterated in confidence-DESC order; a counterpart is included only while
`char_estimate + item_chars <= max_packet_chars` (the anchor + highest-confidence counterpart are
always kept). Overflowing lower-confidence items are excluded; `excluded_item_count` and `truncated`
are reported accurately (replacing the prior no-op `0`).

### 3. Relationship-scoring precision — `relationship_scoring.score_email_calendar_relationship`
- `shared_record_reference` now fires only on a **specific** identifier (`_SPECIFIC_RECORD_RE`, e.g.
  `RFI 42`, `submittal 03`) present in both texts. Generic terms (`bid`, `proposal`, `meeting`,
  `agenda`, `review`, `coordination`) no longer contribute on their own.
- **Anchor gate:** `anchor_present = same_project OR near_exact_subject(Jaccard ≥ 0.6) OR
  (time_proximity AND participant_overlap) OR specific_shared_record`. Without an anchor the confidence
  is capped at `0.40` (weak) — generic internal-domain participant overlap alone can never reach
  moderate. `anchor_present` is surfaced in the result.

### 4. Combined extraction defaults to strong — `build_related_context_action_packet`
Default `min_confidence` is now `STRONG_THRESHOLD` (0.80). `allow_moderate=True` lowers the floor to
moderate and marks the packet `review_only=true` / `review_required=true`.
`find_email_calendar_relationships` keeps a moderate floor for inspection listing.

### 5. Per-ref source-family attribution — `extract_action_candidates_from_raw`
Each persisted `candidate_source_refs` row takes the `source_family` of ITS matching excerpt (email
vs calendar), instead of inferring email whenever any email excerpt exists. A candidate citing both an
email message and a calendar event attributes each ref correctly.

### 6. Live-extraction diagnostics — `extract_action_candidates_from_raw`
A no-output run returns a redacted `diagnostics` block: `model_name` (client model / `"mock"` / None),
`profile_id` (None — client-based path), `prompt_char_count`, `packet_char_estimate`,
`endpoint_reachable` (False for unreachable error classes, True if reached-but-unusable, None when no
client), and `error_class_redacted` (exception **type name only** — no message/body/URL/token).
`_run_with_retry_repair` now returns `(text, error_class)`. `extract-packet --mock-output` remains the
deterministic offline validation path.

### CLI clarity — `phase-10 extract-packet`
`--dry-run/--apply` flag pair (dry-run default, explicit help); added `--allow-moderate` (related,
review-only); payload surfaces `blocked`, and the report carries `note`/`best_confidence`/`diagnostics`.

## Tests

Extended the Phase 10A suites: blocked-related-skips-model, per-ref source-family attribution, no-output
diagnostics, anchor-gate precision (participant-only weak, generic-term weak, specific-record anchor),
strong-default combine + `allow_moderate` review-only, related-packet budget exclusion, and a CLI
dry-run-default test. MCP no-raw/no-writeback, `second_brain_no_writeback_proof`, and `phase_10_schema`
remain green.

## Guardrails

Dry-run default; `--apply` explicit; combined extraction strong-by-default; moderate review-only; no
model call on blocked packets; diagnostics redacted (type names / counts / bools only). No email send /
calendar mutation / Procore writeback / external writeback / cloud-LLM / MCP-raw. No migration, no new
candidate table, no README/ledger bump.
