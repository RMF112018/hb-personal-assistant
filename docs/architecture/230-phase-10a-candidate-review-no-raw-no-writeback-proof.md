# 230. Phase 10A — Candidate review no-raw / no-writeback proof coverage

Date: 2026-06-08

Package: HB Construction Intelligence — Phase 10A Candidate Review CLI Implementation Package (repo-truth update)

## Context

The candidate review feature (records 223–229) is complete. This record adds the
explicit, review-specific guardrail **proof** coverage required by Prompt 08: that
the review CLI exposes no raw content and performs no external writeback.

The package's validation command already passed before this change (64 tests) —
notably `test_second_brain_no_writeback_proof.py`, whose builder dynamically
enumerates every `construction/second_brain/**/*.py` and therefore already scans
`candidate_review.py` for mutation / dangerous imports / secrets. The gap was that
the review surface had no *named, intentional* proof of its own. Scope was
confirmed **lightweight** (named tests + evidence doc, no new proof-builder module
or CLI proof command, since the repo-wide scan already covers the module).

## Decision

Two named proofs added to `tests/test_phase_10a_candidate_review.py`:

- **`test_candidate_review_and_cli_import_no_external_write_surface`** — AST-parses
  the service module **and** the review CLI functions/helpers
  (`review_list/show/summary_cmd/accept/ignore/reject/snooze/edit/export`,
  `_run_review_action`/`_run_review_batch`/`_dispatch_review_action`) and asserts no
  imported module matches a forbidden external-write / raw-exposure substring
  (`graph`, `procore`, `msal`, `requests`, `httpx`, `urllib`, `smtplib`, `aiohttp`,
  `boto`, `mcp`, `packet_builders`). Working over AST **imports** (not raw text)
  means guardrail flag names (`no_graph_or_procore_writeback`) and docstring prose
  ("Procore"/"calendar") don't false-positive, and the local
  `raw_action_intelligence` redaction helper is correctly allowed.
- **`test_no_raw_persisted_in_candidate_review_tables`** — after accept + edit +
  snooze, scans every TEXT cell of the four candidate-review tables for raw markers
  (`http://`/`https://`/`-----BEGIN`/`PRIVATE KEY`/`access_token`/`bearer `),
  proving persistence carries no raw bodies/prompts/responses/URLs/tokens (the prior
  tests only checked emitted output keys).

The other three required-scope items already had coverage: output-key no-raw guards,
the `_P10_GUARDS`-zero attestation (record 229), and export redaction.

Companion evidence:
`docs/evidence/construction-intelligence-phase-10a-candidate-review-cli/01-no-raw-no-writeback-proof.md`
(required-scope → proving-test map, guard-column attestation, structural-coverage
note, validation result).

## Verified

The package's exact validation command —
`pytest tests/test_phase_08d_no_raw_access.py tests/test_phase_08d_no_writeback.py
tests/test_second_brain_no_writeback_proof.py tests/test_phase_10a_candidate_review.py
tests/test_phase_10a_candidate_review_cli.py` — **66 passed** (was 64; +2). `ruff`
clean. The two new proofs confirm the review service + CLI import no external-write
surface and persist no raw content.

## Guardrails / non-goals

Tests + docs only — no production code change; no new proof-builder module or CLI
proof command (the repo-wide second-brain scan already covers the module). No new
migration; no extraction prompt/model/stable-key change; no packet-scope broadening.
No email/calendar/Graph/Procore/external writeback; the proofs scan for, but never
echo, offending text.
