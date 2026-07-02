# Phase 10L — Gap Closure + Hardening (A + B + C) — Evidence

Tooling + tests + **synthetic dry-run** evidence only. **No live DB, vault, source corpus, runtime
JSON, or queue was mutated.** All numbers below come from a throwaway temp DB + temp vault seeded with
synthetic rows (no real corpus/email/Ollama).

## What was implemented
- **10L-A** `scripts/obsidian_vault_db_reconcile.py` (read-only, count-only) +
  `scripts/obsidian_generated_artifact_db_reset.py` (dry-run default; guarded `--apply` flips missing-file
  generated-note rows to `not_generated`; mandatory backup + echo-back confirm flags; source rows &
  queue proven unchanged; summaries reset only for unambiguously-orphaned sources).
- **10L-B** `src/hb_assistant/obsidian_mcp/source_archive_paths.py` centralizes Email Archive routing.
  Archive notes now route `Email Archive/{Work,Home,Shared}/…` (no `Work/Work` double domain). Attachments
  are per-domain (`Email Archive/{Work,Home,Shared}/Attachments/`); the work root is byte-identical to the
  pre-10L layout. Legacy double-domain paths are detected; self-index guard covers all archive roots.
- **10L-C** `scripts/obsidian_folder_readme_upsert.py` upserts the six singleton folder READMEs by exact
  path (never `README__<sha>.md`), protects manual READMEs (generated-marker gate), and reports duplicate
  README variants count-only.
- Redaction checker `scripts/obsidian_evidence_redaction_check.py`.

## What was NOT changed (deferred to continuation — see docs/implementation/obsidian/)
- 10L-D duplicate collapse (grouping layer / `V98` columns / managed blocks): **advisory report only**.
- 10L-E update-history blocks; 10L-F dynamic Ollama classifier; 10L-G MCP query tools; 10L-H operator UI.
- Live per-domain attachment wiring in the 10F extraction pipeline (would change work attachment
  `source_id`s) — capability + guard landed; live wiring deferred.

## Evidence index
- `01-db-vault-reconcile/` — count-only reconcile of the synthetic drift.
- `02-generated-artifact-db-reset/` — dry-run reset plan (no apply performed here).
- `03-email-archive-routing/` — corrected routing + attachment roots + legacy detection proof.
- `04-readme-singleton/` — README upsert dry-run plan.
- `10-tests/` — pytest summary. `11-redaction/` — redaction-checker result.
- `local-sensitive/` — git-ignored row-level detail (NOT committed).
