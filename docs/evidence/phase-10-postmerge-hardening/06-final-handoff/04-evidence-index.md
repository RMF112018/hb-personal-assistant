# Evidence Index — Phase 10 Post-Merge Hardening

Root: `docs/evidence/phase-10-postmerge-hardening/`

- `00-branch-and-baseline.md` — repo truth, branch/baseline, prod DB sha256 baseline.
- `01-postmerge-evidence-repair/` — repaired audit handoff/commit-log/safety-matrix/runbook/
  git-status; README + final-output + validation + safety + changed-files.
- `02-cli-human-output-flags/` — `--no-json` enablement; captured Markdown output for both verbs.
- `03-followup-watch-quality-gate/` — quality-gate persistence proof (temp DB) + tests.
- `04-file-parse-hash-contract/` — hash-contract proof + renamed-field CLI capture.
- `05-validation-and-safety/` — consolidated validation matrix, test/compile logs, CLI smoke,
  production-db-unchanged proof, safety scan.
- `06-final-handoff/` — this bundle.

Repaired prior-phase evidence (under `phase-10-full-candidate-implementation/`):
- `10-final-integration-audit/` — 01/02/07/10/13 corrected to post-merge truth.
- `09-document-file-parsing/` — 01/02/03/04/05/06/08 updated to `text_excerpt_hash` + `hash_scope`.

Architecture: `docs/architecture/239-phase-10-full-candidate-read-model-and-report-surfaces.md`
(post-merge hardening section appended).
