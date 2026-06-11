You are working with Bobby on the `RMF112018/hb-personal-assistant` repository.

Execute the objective defined at:

`docs/planning/phase-10-candidate-lifecycle-review-queue-package/README.md`

Requirements:

- Start with the repo-truth audit in `prompts/00_repo_truth_audit.md`.
- Do not modify production DB during validation.
- Use `/tmp` DB copies for all apply/idempotency checks.
- Do not send or draft emails.
- Do not mutate calendar, Graph, Procore, SharePoint, OneDrive, Obsidian, or any external system.
- Do not expose raw private content.
- Preserve existing Phase 10A task/commitment review behavior.
- Prefer an append-only lifecycle overlay and read model; add schema only if repo truth proves it is necessary.
- Produce raw-free evidence and the final handoff required by `FINAL_HANDOFF_TEMPLATE.md`.

Proceed through the prompt sequence in order and stop only on a documented stop condition.

