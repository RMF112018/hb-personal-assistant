# Prompt 08 — No Raw / No Writeback Proofs

## Objective

Update or add guardrail proof coverage showing the review CLI does not expose raw content or perform external writeback.


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


## Required proof scope

- Candidate review output contains no raw email body/prompt/response.
- Review state transitions do not call Graph/Procore/email/calendar write paths.
- Guard columns remain zero after review actions.
- Export is redacted/safe.

## Validation

```bash
pytest tests/test_phase_08d_no_raw_access.py tests/test_phase_08d_no_writeback.py tests/test_second_brain_no_writeback_proof.py tests/test_phase_10a_candidate_review.py tests/test_phase_10a_candidate_review_cli.py
```
