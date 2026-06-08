# Prompt 02 — Review Service Contracts

## Objective

Create the service layer for candidate review commands without tying business logic directly to Typer handlers.


## Repo-truth baseline

- Repository: `RMF112018/hb-personal-assistant`
- Current audited schema head: `V42`; local agent must rebaseline.
- Target update: Phase 10A Candidate Review CLI.
- Current batch command path observed: `hb-assistant second-brain extract-packets`.
- Review workflow must operate only on persisted local candidate rows.
- Local dirty state and exact HEAD are not verifiable from this package; run `git status --short` and `git rev-parse HEAD` before editing.

Repository truth is authoritative. Stop and report if the local repo materially differs from this package.

## Global guardrails

- No email send.
- No calendar mutation.
- No Graph writeback.
- No Procore writeback.
- No external/cloud LLM dependency.
- No raw email body, raw document text, raw calendar payload, raw Procore payload, raw prompt, raw response, signed URL, download URL, token, or secret persistence/output.
- Do not broaden packet extraction scope.
- Do not alter Phase 10A extraction prompt/model/stable-key behavior unless a test failure proves a direct compatibility issue.
- Review actions are local DB updates only.


## Files likely affected

- `src/hb_assistant/construction/second_brain/local_ai/candidate_review.py`
- `tests/test_phase_10a_candidate_review.py`

## Service functions

Implement `list_review_candidates`, `show_review_candidate`, `accept_candidate`, `ignore_candidate`, `reject_candidate`, `snooze_candidate`, `edit_candidate`, `export_review_queue`, and `review_summary`.

## Contract behavior

Normalize `ignored` to `suppressed`, validate enums, return safe dictionaries, preserve source refs, and never include raw prompt/body/response.
