You are working with Bobby on the `RMF112018/hb-personal-assistant` repository.

Execute the objective defined at:

`docs/planning/phase-10-email-followup-candidate-projection-package/README.md`

Hard constraints:

- Start from repo truth.
- Do not work on `main`.
- Do not mutate the production DB.
- Use `/tmp` DB copies for all DB validation.
- Do not send, draft, reply to, forward, or modify emails.
- Do not create, update, delete, or respond to calendar events.
- Do not perform Graph, Procore, SharePoint, OneDrive, Obsidian, or external-system writeback.
- Do not expose raw email bodies, HTML, private URLs, tokens, secrets, full recipient arrays, unbounded subjects, model prompts, or model responses.
- Implement deterministic behavior first.
- Persist candidates idempotently.
- Attach source refs to every email-derived daily-brief candidate.
- Preserve project-key honesty; unresolved project-like candidates go to review instead of invented keys.
- Extend daily brief and usefulness-gate behavior so email/follow-up projection cannot silently fail.
- Fix or explicitly quarantine the pre-existing deterministic `test_phase_10_email_task_extraction.py::test_commitment_persists_to_commitment_table` failure based on repo truth.

Execution order:

1. Read `README.md`.
2. Read `SCOPE_LOCKS.md`.
3. Execute prompts `00` through `11` in numeric order.
4. Validate against `VALIDATION_MATRIX.md`.
5. Produce the final handoff using `FINAL_HANDOFF_TEMPLATE.md`.

Do not skip evidence. Do not claim merge readiness unless every merge-blocking gate passes.
