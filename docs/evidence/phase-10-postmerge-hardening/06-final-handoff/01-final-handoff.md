# Phase 10 Post-Merge Hardening — Final Handoff

## Branch + HEAD
- Branch: `fix/phase-10-postmerge-hardening`
- Base: `main` @ `483e090d` (PR #13 merge commit); branch cut from there.
- Final HEAD: `45fc3870` (before this handoff commit) → updated to the handoff commit on commit of
  `06-final-handoff`.
- Relationship: branch is `main` + 6 hardening commits (becomes 7 with this handoff commit); `main`
  is unchanged by this branch.

## Commits (6, + this handoff commit)
```
45fc3870 docs(architecture): record phase 10 post-merge hardening contracts
5f061033 test(second-brain): add phase 10 post-merge hardening validation
9ccdbc48 fix(files): clarify phase 10 parse hash contract
965b2c4c fix(second-brain): gate follow-up watch persistence on quality flags
8bed66cd fix(cli): align phase 10 operator markdown flags
ae775cdd docs(second-brain): repair phase 10 post-merge evidence
```

## Files changed (cumulative `main..HEAD`)
Source (4): `cli/files.py`, `cli/second_brain.py`,
`construction/second_brain/local_ai/follow_up_watch.py`,
`construction/second_brain/local_ai/file_parse_read_model.py`.
Tests (3): `test_phase_10_file_parse_read_model.py`, `test_phase_10_follow_up_watch_report.py`,
`test_phase_10_mcp_packet_hardening.py`.
Docs: `docs/architecture/239-…md`; repaired `…/10-final-integration-audit/` (5 files) and
`…/09-document-file-parsing/` (7 files); new `docs/evidence/phase-10-postmerge-hardening/` (6 dirs).

## Hardening fixes (one per prompt)
1. **Evidence + runbook repair (docs)** — audit handoff/commit-log/safety-matrix/runbook/git-status
   now reflect PR #13 merged into `main` (483e090d); branch-final HEAD `f7061ab3` distinguished from
   the merge commit; bearer-shaped test value noted as runtime-constructed; runbook `--no-json`
   commands labeled "expected after Prompt 02".
2. **CLI human-output flags (code)** — `files parse-index` and `daily-brief mcp-packet` gain the
   paired `--json/--no-json` flag (Markdown render path already existed). 2 new CLI tests.
3. **Follow-up watch quality gate (code)** — `run_follow_up_watch_scan` now refuses to persist a
   source-linked but quality-flagged (e.g. contradictory) item, matching the report's `needs_review`
   routing. New `skipped_quality_flags` counter + `quality_gated` guardrail. 1 new test + temp-DB proof.
4. **File-parse hash contract (code)** — `text_hash` → `text_excerpt_hash` + `hash_scope:
   "text_excerpt"` (hash covers the bounded excerpt). Markdown shows `excerpt-hash:`. Phase 09
   evidence updated. Consumer grep proves no dependency on the old field.
5. **Validation + safety sweep (evidence)** — consolidated proofs.
6. **Final handoff (evidence)** — this bundle.

## Validation
- `compileall -q src tests` → OK.
- `pytest` (mcp_packet_hardening + file_parse_read_model + follow_up_watch_report) → **14 passed**.
- CLI smoke (parse-index + mcp-packet, `--json`/`--no-json`, temp DB) → exit 0, correct output.
- Changed-file `ruff` + `mypy` → clean (4 modules).
- See `06-validation-summary.md` and `05-validation-and-safety/`.

## Safety
- Forbidden-content scan over both evidence trees → **PASS**, 0 content matches (1 documented safe
  match: the scan command itself). No raw bodies/URLs/tokens/emails. See `07-safety-summary.md`.

## Production DB
- sha256 before == after == `f93b7808…4759` → **UNCHANGED**. No migration (schema stays V45). All
  proof work used disposable temp DBs.

## Known limitations
See `08-known-limitations.md`. No new product scope; pre-existing broad-suite failures and
unrelated lint (cli/procore.py B008) untouched; mcp-packet counts reflect the deterministic context
builder.

## Merge recommendation
**MERGE-READY.** No stop condition triggered. Surgical, additive, read-only/dry-run; no schema
change; no external writeback; production DB unchanged. See `09-merge-readiness-assessment.md`.

## PR command
```bash
git push -u origin fix/phase-10-postmerge-hardening
gh pr create --base main --head fix/phase-10-postmerge-hardening \
  --title "Phase 10 post-merge hardening (evidence repair + CLI flags + watch quality gate + hash contract)" \
  --body-file docs/evidence/phase-10-postmerge-hardening/06-final-handoff/01-final-handoff.md
```
