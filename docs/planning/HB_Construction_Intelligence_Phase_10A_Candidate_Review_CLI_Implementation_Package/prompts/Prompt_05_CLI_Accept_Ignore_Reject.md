# Prompt 05 — CLI Accept, Ignore, and Reject

## Objective

Implement local-only candidate review state transitions.


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


## Commands

```bash
hb-assistant second-brain review accept --candidate-id <candidate_id> --json
hb-assistant second-brain review ignore --candidate-id <candidate_id> --reason "not actionable" --json
hb-assistant second-brain review reject --candidate-id <candidate_id> --reason "incorrect extraction" --json
```

Each action writes a review event, preserves source refs, updates local review metadata only, and performs no external writeback.
