# 05 — Validation and Evidence Plan

## Full Validation Command Set

Run and capture:

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
mypy src

.venv/bin/hb-assistant --version
.venv/bin/hb-assistant diagnostics env --json
.venv/bin/hb-assistant diagnostics paths --json
.venv/bin/hb-assistant diagnostics automation --json
.venv/bin/hb-assistant actions extract --dry-run --json
.venv/bin/hb-assistant actions list --json
.venv/bin/hb-assistant run morning --dry-run --json
.venv/bin/hb-assistant diagnostics scan-sensitive --repo . --json
```

## Evidence Output Requirements

All evidence should be redacted and safe to commit.

```text
docs/evidence/mvp-local-runtime/
  00-repo-truth.md
  01-morning-run-action-extraction-audit.md
  02-dry-run-policy-proof.md
  03-obsidian-written-to-note-proof.md
  04-workstream-context-mentions-proof.md
  05-validation-scope-hardening.md
  06-local-runtime-evidence-harness.md
  07-operator-runbook-and-limitations.md
  08-final-mvp-candidate-closeout.md
  outputs/
```

## Command Output Storage

Store command outputs as:

```text
outputs/pytest.txt
outputs/ruff.txt
outputs/mypy.txt
outputs/version.txt
outputs/diagnostics-env.json
outputs/diagnostics-paths.json
outputs/diagnostics-automation.json
outputs/actions-extract-dry-run.json
outputs/actions-list.json
outputs/run-morning-dry-run.json
outputs/scan-sensitive.json
```

## Failure Handling

If a command fails:

1. Preserve raw output in the relevant `outputs/` file.
2. Classify failure:
   - code defect;
   - local environment/path issue;
   - external Graph/admin-consent blocker;
   - intentionally deferred;
   - validation-scope limitation.
3. Patch if it is a local MVP defect.
4. Document if intentionally deferred.

## Final Status Vocabulary

Use one of:

```text
MVP_CANDIDATE_LOCAL_RUNTIME_READY
MVP_CANDIDATE_WITH_LOCAL_GAPS
LOCAL_RUNTIME_BLOCKED
GRAPH_DELEGATED_PROOF_DEFERRED_PENDING_ADMIN_CONSENT
```
