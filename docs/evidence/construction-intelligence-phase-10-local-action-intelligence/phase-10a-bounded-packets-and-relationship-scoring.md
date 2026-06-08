# Phase 10A — Bounded Packets + Relationship Scoring (evidence)

Date: 2026-06-08 · Local-only · Dry-run default · No external writeback · No raw-content leakage

## Acceptance criteria

| Criterion | Result | Evidence |
| --- | --- | --- |
| Builders no longer emit broad unrelated raw dumps for extraction | PASS | scoped builders return ONE thread / ONE event; `test_phase_10a_packet_scope` |
| Action extraction defaults to one coherent unit per packet | PASS | `extract-packet` builds one packet/invocation; `extract_actions_for_packet` |
| Combined email/calendar packets require deterministic relationship evidence | PASS | `build_related_context_action_packet` compiles only at ≥0.55; blocked envelope below; `test_phase_10a_packet_scope::test_unrelated_records_are_not_combined` |
| Packets normalized, bounded, stripped of full HTML/Teams boilerplate | PASS | `normalize_model_text` + `test_phase_10a_packet_normalization` (join URL/Meeting ID/Passcode/dial-in/Teams removed) |
| Packet purpose controls allowed outputs | PASS | `PACKET_TYPE_PURPOSE`/`PURPOSE_ALLOWED_OUTPUTS`; triage `allowed_outputs=["triage_labels"]` |
| Operator can inspect packets + relationship reason codes via CLI JSON | PASS | `raw-email-packet`/`raw-calendar-packet`/`relationship-candidates`/`extract-packet --json` |
| New + targeted existing tests pass | PASS | see Validation |

## Relationship scoring (deterministic)

Features → `score_components`: same_project, subject_similarity, explicit_meeting_reference,
participant_overlap, time_proximity (24h/72h), shared_record_reference, teams_join_reference_match,
generic_title_penalty, private_sensitive_penalty. Classification: **≥0.80 strong**, **0.55–<0.80
moderate (review_required)**, **<0.55 weak (no combine)**. Verified:
- title+ref+participant+time → strong (1.0); same-project-only → weak (0.25); generic title penalized
  (specific 1.0 vs generic 0.8); moderate (0.6) → review_required. Contract⇄module parity asserted.

## Normalization / redaction

- HTML-only bodies → `body_text_normalized` (reuses stdlib `html_to_text`).
- Removed from model text: Teams boilerplate, join URLs, Meeting IDs, Passcodes, dial-in numbers,
  Microsoft divider lines, HTML tags. `has_join_url` kept as metadata (URL never emitted).
- Attendees summarized to `{attendee_count, user_is_attendee, participant_domains}` — no large arrays.

## Budgeting

Hard caps per packet type (email_thread ≤6 msgs/≤1200 chars/msg/≤12000; calendar_event ≤1200/≤6000;
related ≤1 thread+≤3 events/≤12000; triage ≤20 items/≤500 chars/≤12000). Truncate at item boundaries
then char-truncate with `[truncated]`; report `truncated`, `excluded_item_count`, `char_estimate`,
`token_estimate`. Deterministic (same packet_id + budget on re-build).

## Safety

- Extraction dry-run (default) writes nothing to task_candidates / commitment_candidates /
  candidate_source_refs / local_model_run_receipts.
- Triage packets never persist candidates (`extracted=false`, `note=purpose_does_not_allow_candidate_actions`),
  even on `--apply`.
- Apply persists only after schema + business-rule validation; generic/vague actions rejected.
- `candidate_source_refs.candidate_id` == persisted candidate id; SHA-256 stable keys; source refs
  resolve back to raw message/event refs. Guard columns sum to 0.

## Validation

```
compileall src tests …………………………………… OK
ruff (new modules + tests) ………………………… clean
mypy (packet_normalize, relationship_scoring, packet_builders, raw_action_intelligence) … Success
pytest (147) packet_scope + relationship_scoring + packet_normalization + packet_budget +
  packet_extraction_safety + raw_model_context_packets + raw_action_intelligence +
  raw_extraction_hardening + phase_10_schema + phase_08d_no_raw_access + phase_08d_no_writeback +
  second_brain_no_writeback_proof + phase_10_contracts + email_task_extraction + ai_jobs +
  fixture_runner + structured_output ……… all pass
CLI: relationship-candidates / raw-email-packet / extract-packet --triage … exit 0
```

MCP no-raw / no-writeback and Phase 10 schema-status remain green (a `.update()` call in the packet
envelope was rewritten as a dict-merge to satisfy the no-writeback static scanner).

## Guardrails

Local-only; advisory; dry-run default; deterministic relationship linking; packet purpose controls
allowed outputs; triage never persists. No email send / calendar mutation / Procore writeback /
external writeback / cloud-LLM / MCP raw exposure. Full HTML / join URLs / full attendee arrays stay in
the raw V42 tables only.
