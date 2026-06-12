You are working with Bobby on the `RMF112018/hb-personal-assistant` repository.

Execute the objective defined at:

`docs/planning/phase-10-daily-brief-effectiveness-ranking-policy-telemetry-package/README.md`

Hard constraints:

- Start from repo truth.
- Do not work on `main`.
- Do not mutate the production DB.
- Use `/tmp` DB copies for all DB validation.
- Do not send, draft, reply to, forward, archive, delete, label, or modify emails.
- Do not create, update, delete, or respond to calendar events.
- Do not perform Graph, Procore, SharePoint, OneDrive, Obsidian, or external-system writeback.
- Do not mutate lifecycle state or source refs from telemetry.
- Do not expose raw email bodies, HTML, calendar bodies, attendees, Procore payloads, private URLs, tokens, secrets, local paths, full recipient arrays, unbounded subjects, model prompts, or model responses.
- Implement deterministic evaluation first.
- Treat all model-derived metrics as advisory and observational only.
- Apply requires explicit `--max-persist` and `/tmp` DB copy.
- Dry-run must write zero rows.
- Stop if the ranking/assembly prerequisite slice is not present in repo truth.

Execution order:

1. Read `README.md`.
2. Read `SCOPE_LOCKS.md`.
3. Execute prompts `00` through `16` in numeric order.
4. Validate against `VALIDATION_MATRIX.md`.
5. Produce the final handoff using `FINAL_HANDOFF_TEMPLATE.md`.

Do not skip evidence. Do not claim merge readiness unless every merge-blocking gate passes.
