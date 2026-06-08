# Prompt 01 — Schema V43 Candidate Review Migration

## Objective

Implement the smallest additive schema migration required for snooze/edit/auditability.


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

- `src/hb_assistant/store/migrator.py`
- `tests/test_phase_10_schema.py`

## Implementation steps

1. Reconfirm current schema head is V42.
2. Add V43 migration statements.
3. Add nullable columns to both candidate tables: `snoozed_until_utc`, `reviewed_utc`, `reviewed_by`, `review_note_redacted`.
4. Add nullable columns to `candidate_review_events`: `changes_json_redacted`, `snoozed_until_utc`, `reviewer_ref`.
5. Add review/snooze indexes if consistent with migrator style.
6. Update schema tests.

## Validation

```bash
python -m compileall src tests
pytest tests/test_phase_10_schema.py
```
