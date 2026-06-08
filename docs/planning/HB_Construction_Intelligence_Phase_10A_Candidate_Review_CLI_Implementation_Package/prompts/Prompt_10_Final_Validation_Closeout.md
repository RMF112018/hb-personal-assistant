# Prompt 10 — Final Validation, Closeout, and Handoff

## Objective

Run final validation and prepare the implementation handoff.


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


## Required commands

```bash
python -m compileall src tests
ruff check src/hb_assistant/construction/second_brain src/hb_assistant/cli tests
mypy src/hb_assistant/construction/second_brain
pytest   tests/test_phase_10a_candidate_review.py   tests/test_phase_10a_candidate_review_cli.py   tests/test_phase_10a_batch_extraction.py   tests/test_phase_10a_packet_extraction_safety.py   tests/test_phase_10a_raw_action_intelligence.py   tests/test_phase_10_schema.py   tests/test_phase_08d_no_raw_access.py   tests/test_phase_08d_no_writeback.py   tests/test_second_brain_no_writeback_proof.py
```

Use `21_FINAL_HANDOFF_TEMPLATE.md` for final response.
