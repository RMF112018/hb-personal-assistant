# Stop Conditions

Stop and report immediately if any of the following occurs.

## Raw/private content leakage

- Raw email bodies, raw calendar bodies, raw HTML, raw prompts, raw model responses, full attendee arrays, full recipient arrays, private subjects/titles, join URLs, signed URLs, download URLs, cookies, tokens, secrets, API keys, or credential-shaped strings appear in repo evidence, committed tests, docs, logs, browser proof, Obsidian proof, or JSON proof.
- A command prints raw values while generating evidence.
- A fixture uses real private content instead of synthetic safe content.

## External mutation/writeback

- Any email send/draft/archive/delete/label mutation is invoked.
- Any calendar create/update/delete/respond mutation is invoked.
- Any Procore writeback path is invoked.
- Any Graph writeback path is invoked.
- Any external writeback path is invoked.

## Production DB safety

- Production DB hash, size, or mtime changes during validation.
- A validation command is about to run with `--apply` against the production DB instead of a `/tmp` copy.
- A migration is needed but cannot be proven additive/idempotent/non-destructive.

## Architecture/scope

- The implementation requires a cloud LLM fallback.
- The implementation would make raw bodies or join URLs part of structured projection tables or outbound read models.
- Candidate rows can be persisted without source refs.
- Daily-run clean success is still possible when useful source rows exist but daily candidates are empty.
- Procore aggregate sludge is promoted as executive action rows without why-today evidence.
- The browser auto-opens during scheduled validation.

## Quality

- Targeted tests fail because of this package and cannot be corrected inside scope.
- Static validation reveals unresolved raw-leak or writeback risk.
- The local agent cannot produce the required evidence bundle.
