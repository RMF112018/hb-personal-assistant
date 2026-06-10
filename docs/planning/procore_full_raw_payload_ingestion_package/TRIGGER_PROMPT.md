You are working with Bobby on repository:

`RMF112018/hb-personal-assistant`

Local repo path:

`/Users/bobbyfetting/hb-personal-assistant`

Execute the one-shot implementation package defined at:

`docs/planning/procore_full_raw_payload_ingestion_package/README.md`

Objective:

Implement the change from redacted Procore replay to fully populated Procore raw/structured analytics storage. `procore_endpoint_raw_payloads.payload_json` and matching `procore_raw_*` structured rows must be populated from full live Procore endpoint response payload values, not from `procore_live_records.canonical_json_redacted`.

Hard constraints:

- Create a new branch from current `main`.
- Do not mutate production DB during validation.
- Use `/tmp` DB copies and fixture-backed tests.
- Do not commit DB files, raw payload dumps, secrets, tokens, signed URLs, `.env`, `.sqlite`, `.db`, `.pyc`, or cache artifacts.
- Do not emit raw payload bodies to repo evidence, CLI stdout, logs, daily brief, Obsidian, browser/status surfaces, or test snapshots.
- Redaction is only for outbound surfaces; private local SQLite should preserve full endpoint business payloads.
- Transport/auth secrets must never be stored.

Follow prompts 00 through 07 in order. Commit and push the completed branch. Return a final handoff with branch, commit SHA, changed files, validation, evidence path, safety proof, and exact post-merge production apply commands.
