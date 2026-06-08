# 215. Phase 10A — Live extract-packet wiring + packet-driven source-family attribution

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10 / 10A Local Action Intelligence (repo-truth update)

## Context

Follow-up to ADR 214. Two blockers remained before live apply-path testing: (a) source-family
attribution used a string heuristic, so a model citing a *thread* ref was mis-attributed to
`calendar_event_raw_content`; and (b) `extract-packet` had no live model client — without
`--mock-output` it returned the misleading "model returned no output" though no model was called.

## Decision

### 1. Packet-driven source-family attribution — `raw_action_intelligence.py`
`extract_action_candidates_from_raw` takes `source_family_map` (built by `extract_actions_for_packet`
from `packet["source_refs"]`). A merged `known_family = {**excerpt_family, **source_family_map}` is the
authoritative per-ref family: thread → `email_thread_raw_context`, message → `email_message_raw_content`,
event → `calendar_event_raw_content` — no string guessing, no calendar fallback. Each candidate's
`source_refs` are validated against `known_family` in the accept phase (dry-run and apply); a candidate
citing an unknown ref is rejected (`source_ref_not_in_packet`). Persistence writes
`known_family[ref]` as `source_family`.

### 2. No-client short-circuit — `raw_action_intelligence.py`
When `client is None and mock_output is None`, the extractor returns immediately with
`note="no_model_client"` and a `no_client_constructed` diagnostic — it never claims "model returned no
output" when no model was called.

### 3. Live client resolver — `provider.py`
`resolve_local_model_client(*, provider="ollama", profile_id="default_extract", model=None,
timeout_seconds=None, profiles=None) -> (client|None, model_name|None, reason|None)` constructs an
`OllamaChatClient` (default model from the `default_extract` profile → `mistral-nemo:12b`; `--model`
override; profile timeout unless overridden). Returns a safe reason
(`unsupported_provider`/`unknown_profile`/`live_model_client_missing`) when no client can be built.
Construction does not touch the daemon, so it is unit-testable.

### 4. Diagnostics reasons — `raw_action_intelligence.py`
`_diagnostic_reason(...)` classifies every run into one safe reason: `no_client_constructed`,
`model_timeout`, `ollama_unreachable`, `schema_rejected_output`, `invalid_json_output`,
`empty_model_output`, or `None` (success). `_build_diagnostics(...)` attaches
`{model_name, profile_id, prompt_char_count, packet_char_estimate, endpoint_reachable,
error_class_redacted, reason}` to the no-client, no-output, and final reports. `error_class_redacted`
is the `OllamaUnavailable` category code (e.g. `ollama_request_failed`) or the exception type name —
never a message/body/URL/token. `_run_with_retry_repair` now returns `(text, error_class, is_timeout)`.

### 5. CLI `phase-10 extract-packet` — `cli/second_brain.py`
Adds `--profile` (default `default_extract`), `--model` (override), `--provider` (default `ollama`),
`--timeout-seconds`, and a hidden test-only `--no-client`. Without `--mock-output`/`--no-client` it
resolves a live client via `resolve_local_model_client`; if none can be built it emits
`error="live_model_client_missing"` and exits before extraction. The payload surfaces `model_name`
and `report.diagnostics`.

## Tests

`test_phase_10a_packet_extraction_safety.py`: thread-ref citation → `email_thread_raw_context`;
event-ref → `calendar_event_raw_content`; unknown ref rejected; no-client → `no_client_constructed`
(not "model returned no output"); diagnostic reasons (`empty_model_output`/`invalid_json_output`/
`schema_rejected_output`); CLI live-attempt reports `model_name=mistral-nemo:12b` (never null on a live
attempt); CLI `--no-client` explicit diagnostic. `test_phase_10_local_model_readiness.py`:
`resolve_local_model_client` defaults to `mistral-nemo:12b`, model override, unsupported provider.

## Guardrails

Dry-run default; `--apply` explicit. Diagnostics redacted (type/code names, counts, bools only — no
body/URL/token; `OllamaUnavailable` codes are safe categories). No email/calendar/Procore/external/
cloud-LLM/MCP-raw writeback. No migration, no new candidate table, no README/ledger bump.
