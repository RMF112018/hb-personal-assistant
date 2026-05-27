# Package Index and Execution Order

## Recommended Execution Sequence

1. `prompts/Prompt_00_Repo_Truth_Revalidation.md`
2. `prompts/Prompt_01_Morning_Run_Action_Extraction_Truth_Audit_And_Patch.md`
3. `prompts/Prompt_02_Dry_Run_Semantics_And_Run_Ledger_Policy.md`
4. `prompts/Prompt_03_Obsidian_Written_To_Note_Provenance.md`
5. `prompts/Prompt_04_Workstream_Context_Body_Mentions_Upgrade.md`
6. `prompts/Prompt_05_MVP_Critical_Validation_Scope_Reduction.md`
7. `prompts/Prompt_06_MVP_Local_Runtime_Evidence_Harness.md`
8. `prompts/Prompt_07_MVP_Operator_Runbook_And_Known_Limitations.md`
9. `prompts/Prompt_08_Final_MVP_Candidate_Closeout.md`
10. `prompts/Prompt_09_Deferred_Graph_Consent_Closeout.md` — run only after IT/admin consent is granted.

## Execution Rules

- Each prompt starts by confirming branch, commit, remote, and working tree.
- Each prompt uses narrow, targeted inspection. Do not re-read files already in immediate context.
- Each prompt produces evidence under `docs/evidence/mvp-local-runtime/` or a clearly named subfolder.
- Each prompt commits only intentional source/docs/evidence changes.
- Prompt 09 remains deferred until delegated Graph consent is available.

## Expected Final Evidence Tree

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
    pytest.txt
    ruff.txt
    mypy.txt
    diagnostics-env.json
    diagnostics-paths.json
    diagnostics-automation.json
    actions-extract-dry-run.json
    actions-list.json
    run-morning-dry-run.json
    scan-sensitive.json
```
