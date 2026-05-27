# 09 — Source Truth Checklists

## Code-Truth Checklist

- [ ] `hb-assistant` CLI entry point resolves.
- [ ] `actions` group is registered.
- [ ] `ActionService.extract()` is the service method used by orchestrator.
- [ ] `extract_candidates()` remains lower-level extractor only.
- [ ] `upsert_action_item()` preserves completed status.
- [ ] `link_action()` is idempotent.
- [x] `written_to_note` is allowed and tested.
- [x] `WorkstreamContextBuilder.mentions` is populated.
- [ ] `run morning` classifies Graph blocker correctly.
- [x] `run morning` local stages continue despite missing Graph consent.  # P06 harness (840bc1b)

## Evidence Checklist

- [ ] Repo-truth evidence captured.
- [ ] Validation output captured.
- [ ] Action extraction proof captured.
- [x] Morning dry-run proof captured.  # P06
- [x] Obsidian provenance proof captured.  # P06 marker-bound harness
- [x] Idempotency proof captured.  # P06
- [x] Sensitive scan proof captured.  # P06
- [x] Known limitations documented.  # P06 (Graph deferred)

## Safety Checklist

- [ ] No M365 writeback.
- [ ] No app-only mail/calendar runtime.
- [ ] No full bodies.
- [ ] No full files.
- [ ] No secrets.
- [ ] No private Obsidian content.
- [ ] No raw Graph payloads in evidence.

## P06 — MVP Local Runtime Evidence Harness (840bc1b)
- [x] Deterministic harness (`tests/test_mvp_local_runtime_evidence.py`) created and passing.
- [x] All 7 required fixtures seeded (redacted body mention, waiting-on, action candidate, parser excerpt, file review, upcoming calendar, source links, outside-marker note content).
- [x] 6 proofs executed: actions extract/list dry-run, run morning dry-run, Obsidian marker-bound (dry/apply/preservation/idempotent), full idempotency, sensitive scan.
- [x] Exact outputs written: `docs/evidence/mvp-local-runtime/06-local-runtime-evidence-harness.md` + 5 named JSONs in outputs/.
- [x] No Graph calls; local-only Store + writer + extractor paths only.
- Reference: `docs/evidence/mvp-local-runtime/06-local-runtime-evidence-harness.md` (HEAD 840bc1b post-P05).

## P07 — MVP Operator Runbook and Known Limitations (d15610e)
- [x] `docs/operations/mvp-local-runtime-operator-guide.md` created and covers all 12 mandated topics (venv, diagnostics, morning dry-run, apply/write, what gets written, what never, logs/evidence paths, SQLite/auth/cache locations, disable launchd, inspect errors, Graph/admin blocked items, Prompt 9 post-consent readiness).
- [x] `docs/evidence/mvp-local-runtime/07-operator-runbook-and-limitations.md` (process + 12-topic coverage matrix + starting state) created.
- [x] `docs/evidence/mvp-local-runtime/06-known-limitations.md` (dedicated extractable limitations including Graph deferred + new operational ones) created.
- [x] All examples validated via safe re-runs of documented commands (`diagnostics env/paths/automation`, `run morning --dry-run`, `automation uninstall-launchd --dry-run`).
- [x] Sensitive scan clean on new artifacts (only expected descriptive MSAL indicator in the guide itself; no secrets).
- [x] Internal runbooks/ used via targeted methods only; public canonical guide lives in `docs/operations/`.
- Reference: `docs/operations/mvp-local-runtime-operator-guide.md` + the two 0x- mds (HEAD d15610e post-P06).

## P08 — Final MVP Candidate Closeout (55fbaf1)
- [x] Exact listed commands executed (git status/rev-parse + full pytest/ruff/mypy + hb-assistant --version + diagnostics env/paths/automation --json + actions extract/list + run morning --dry-run --json + diagnostics scan-sensitive --repo . --json) and raw outputs captured.
- [x] `docs/evidence/mvp-local-runtime/08-final-mvp-candidate-closeout.md` created (starting state with actual HEAD, command outputs/excerpts, validation matrix P00–P07, truthful classification, package summary, risks).
- [x] Supporting capture `validation-outputs/08-starting-checks-raw.txt` created.
- [x] Minimal surgical 09 checklist + architecture updates performed (this section + pointers in 13/00-README).
- [x] Sensitive scan on new 08-md + evidence tree: clean (no new real secrets; only pre-existing P05-era findings).
- [x] Verifiers (validation-closeout, sensitive-artifact-scan, check) spawned with identical strict guardrails (targeted only — no read_file on src/ or prior context files).
- Final classification: **MVP_CANDIDATE_LOCAL_RUNTIME_READY** + **GRAPH_DELEGATED_PROOF_DEFERRED_PENDING_ADMIN_CONSENT** (truthful; P06/P07 local proofs solid; P05 pre-existing test/lint issues noted as documented limitations; Graph is the explicit external blocker).
- Reference: `docs/evidence/mvp-local-runtime/08-final-mvp-candidate-closeout.md` (HEAD 55fbaf1 post-P07).
