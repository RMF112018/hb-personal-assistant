# 00 — Repo State (Prompt 00 preflight)

## Branch

- Working branch: `experiment/phase-10-top3-local-model-agent-convergence`
- Created from: `main` @ `ebd8e74a388419606d81685aa48bcd2f5ca764b3`
- `ebd8e74a` = `Merge pull request #14 from RMF112018/fix/phase-10-postmerge-hardening`
- This base intentionally includes the post-merge hardening work (CLI `--json/--no-json`
  flags, follow-up-watch quality-gated persistence, file-parse hash-scope clarification)
  on top of PR #13 (Phase 10 full-candidate implementation).
- `main`, `origin/main`, and `HEAD` all point at `ebd8e74a` at branch creation.

## Phase 10 lineage present on base

- PR #13 — Phase 10 full-candidate implementation (merged).
- PR #14 — post-merge hardening (merged; this is the base).
- Daily-brief intelligence adapter, daily-brief synthesis, and V45 email follow-up raw
  enrichment all present under `src/hb_assistant/construction/second_brain/`.

## Schema

- `LATEST_SCHEMA_VERSION = 45` (`src/hb_assistant/store/migrator.py`).
- V45 table `email_followup_enrichments` present with `_P10_GUARDS` CHECK columns
  (`raw_*_persisted = 0`, `*_writeback_performed = 0`).
- **No migration planned** for this package — the existing V45 surface is sufficient.

## config/config.yml

- Present in working tree but **foreign / untracked** (not in git index). It is never staged.

## Working tree at preflight

- Only untracked `docs/planning/*-package/` directories (planning packages, incl. this one).
  No tracked dirty files. Only files this package creates/edits will be staged.

## Guardrails acknowledged

No `main` edits, no merge/rebase, no cloud LLM, no email/calendar/Procore/Graph/MCP/external
writeback, no production-DB mutation during validation (DB copies only), no raw content in any
committed artifact. All apply paths capped + idempotent + source-linked + fail-closed.
