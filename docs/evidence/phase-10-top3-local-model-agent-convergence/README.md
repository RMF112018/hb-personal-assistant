# Evidence — Phase 10 Top 3 Local-Model Agent Convergence

Branch `experiment/phase-10-top3-local-model-agent-convergence` (base `ebd8e74a`). All evidence is
raw-free (counts, hashes, source ids, redacted `~/…` paths, safe metadata only). Render proofs pass
the runtime egress scan; the bundle passes the forbidden-string scan (`17`).

| File | What it proves |
|---|---|
| 00-repo-state.md | Branch/base, schema head V45, config.yml foreign, no migration planned |
| 01-branch-state.txt | HEAD/base/origin, schema head |
| 02-schema-before-after.json | Schema V45 before/after; migration_added=false |
| 03-current-surface-audit.md | Repo-truth audit of the three candidates (symbol-located) |
| 04-unified-design-contract.md | Converged object/contract, two-call design, validation plan |
| 05-daily-brief-intelligence-convergence-proof.json | Unified MEI object (adapter + pending) |
| 06-browser-model-enriched-intelligence-proof.html | Browser card, exact label, egress-clean |
| 07-obsidian-model-enriched-intelligence-proof.md | Obsidian markdown, exact label |
| 08-status-json-proof.json | Status block (safe counts/metadata only) |
| 09-scheduler-install-preview-proof.json | Install plan: posture, grammar, no auto-open (paths redacted) |
| 10-scheduler-status-proof.json | Status readiness fields + last_run (paths redacted) |
| 11-email-raw-enrichment-eligibility-proof.json | NATURAL readiness on production-copy (pre-seed) |
| 12-email-raw-enrichment-dry-run-proof.json | Seeded-copy dry-run: would_persist, no writes |
| 13-email-raw-enrichment-capped-apply-proof.json | Seeded-copy apply: cap=2 over 3 eligible → persisted 2 |
| 14-email-raw-enrichment-idempotency-proof.json | Seeded-copy rerun: no new rows |
| 15-daily-run-integrated-proof.json | Seeded-copy integrated run: MEI consumed pending, egress clean |
| 16-model-unavailable-fallback-proof.json | MEI withheld+degraded; deterministic brief preserved |
| 17-forbidden-string-scan.txt | Bundle scan CLEAN |
| 18-no-writeback-proof.md | Static + runtime no-writeback proof |
| 19-guard-column-proof.json | V45 guard columns all zero after apply |
| 20-production-db-unchanged-proof.txt | Production DB sha256 unchanged |
| 21-validation-results.md | Tests / ruff / mypy / compile / CLI smoke / DB-copy summary |
| 22-cli-help-snapshots.md | CLI help (flags) for the operator surfaces |
| 23-output-path-safety-proof.md | Repo-contained output refused; non-repo paths; no auto-open |
| 24-known-limitations.md | True residual limitations |
| 25-final-handoff.md | Operator handoff |
| 26-residual-work-audit.md | Residual-work audit result |

Seeded-copy proofs (`12`–`16`, `19`) use clearly-labeled synthetic source-linked fixtures because the
production-copy had no naturally eligible email-source-linked accepted records (`11`). Production DB
is never mutated.
