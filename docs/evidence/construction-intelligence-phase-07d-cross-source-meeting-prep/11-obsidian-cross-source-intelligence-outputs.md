# 07D Prompt 11 — Obsidian Cross-Source Intelligence Outputs (Evidence)

Additive over schema **V25** (no migration). Marker-bounded Obsidian notes for the 07D intelligence,
via a new `construction-agent cross-source obsidian/status` sub-app. Dry-run default (repo evidence
preview + proof, no vault); `--apply` writes the local vault. Run records persist to the V25
`cross_source_intelligence_obsidian_runs` audit table.

## Preflight (repo truth)

- `git rev-parse HEAD` → `fe2f6cd845d3cf9329fe536a749c812ffd9b58a2` (Prompt 10 HEAD).
- `git status --short` → clean (only untracked `.claude/`, `.code-graph/`).
- `python --version` → Python 3.12.11 (`.venv/bin/python3.12`); `hb-assistant --version` → `1.3.0`.
- Schema version → **25**; package version → `1.3.0`.
- Ancestry — all ancestors of HEAD: 07A `3cf1652…`, 07B `748ed7e…`, 07C `733ffed…`.
- Evidence folder present with `00`–`10`; this adds `11` (+ the dry-run preview / proof artifacts).

## What changed

- **Engine** `construction/obsidian/cross_source.py` (+ `__init__.py`): `ObsidianCrossSourceRenderer`
  renders six marker-bounded notes from the six 07D read-model `*_status()` summaries; self-contained
  marker/atomic-write helpers + output-fence; dry-run preview/proof + apply-to-vault; persists a run
  record; `cross_source_obsidian_status()` coverage.
- **Store** `construction/store/repositories.py`: `upsert/list/count_cross_source_intelligence_obsidian_run(s)`.
- **CLI** `cli/construction.py`: `construction-agent cross-source obsidian/status`.
- **Tests** `tests/test_cross_source_obsidian.py` (7).
- Reused unchanged: the six `*_status()` functions, `ConstructionVaultWriter`, `PathPolicy`,
  `hash_value`. `cross_source_intelligence_obsidian_runs` was already registered in the lifecycle
  contract → inventory stays **120**.

## Design grounded in repo truth

- **Source = the six redacted read-model summaries** → no raw content can reach a note (the status
  functions emit only counts/enums/bands/review counts).
- **Marker-bounded** (`HB-CROSS-SOURCE-<KIND>:START/END`) atomic replace preserves user content +
  frontmatter outside the markers (proven idempotent in tests); **output-fence** rejects token/URL/
  PEM/full-text markers on every rendered note.
- **Dry-run default** writes the repo evidence preview + proof and **no vault**; `--apply` writes the
  vault (mutually exclusive flags). Live validation ran **dry-run only** — `--apply` would write the
  operator's real Obsidian vault (outward side effect; per the 07A/07C precedent the real vault is
  left unwritten; the apply path is unit-tested against a temp vault).

## Static + test validation (exit codes)

| Command | Result |
|---|---|
| `python -m compileall src tests` | exit 0 |
| `ruff check .` | exit 0 — All checks passed |
| `mypy src` | exit 0 — no issues in **189** source files |
| `pytest -m "not live and not integration and not manual"` | **2213 passed**, 1 deselected (exit 0) |

(Prompt 10 baseline 2206; +7 new obsidian tests.)

## CLI validation matrix (all exit 0)

`cross-source obsidian --dry-run`, `cross-source status`,
`construction-agent {validate, data-quality gates/no-writeback-proof/table-inventory}`,
`procore validate`, `graph files status/no-writeback-proof`, `graph calendar status`,
`graph mail status` — captured to `/tmp/p11/*.json` (ephemeral, not committed).

### Live `cross-source obsidian --dry-run` (all projects)

- `mode=dry_run`, `notes_planned=6`, `notes_written=0`, `applied_to_vault=False`,
  `review_required_count=2027` (aggregate review-required items across the six read models — dominated
  by the aging layer's 1780; advisory).
- Six rendered sections: relationships, meeting_prep, issue_history, risk_digest, aging_exposure,
  correspondence.
- Wrote `11-obsidian-cross-source-output-preview.md` + `obsidian-cross-source-dry-run.json` to this
  07D evidence folder (committed artifacts). `cross-source status` → `runs=1`, `by_mode={dry_run:1}`.

### Safety invariants

- No-raw-content regex over the serialized `obsidian` + `status` payloads **and** the committed
  preview/proof artifacts → **no match**; output-fence passed on every note.
- All eight guard `CHECK(… = 0)` columns stay 0 on `cross_source_intelligence_obsidian_runs`
  (asserted in tests).
- `data-quality no-writeback-proof` `proof_passed=true`; `graph files no-writeback-proof` `ok=true`.
- `table-inventory` `schema_version=25`, `contract_table_count=120` (no new tables).
- `data-quality gates` `meeting_prep_readiness_claim="ready"` — unchanged.

## Test-path coverage (new file)

dry-run renders six marker-bounded sections + preview/proof; apply writes six vault notes preserving
user content idempotently (re-apply replaces only inner marker content); empty source renders without
crash; review-required surfaced in the run record; no-raw-content (notes + report) + output-fence;
idempotent run record (one row per project+mode), guard columns 0; status coverage.

## Guardrails honored / stop conditions

- No external writeback / write scopes; vault write only on explicit `--apply` (not run live); local
  SQLite writes limited to the audit run record (counts/enums only).
- No raw email/document/calendar content, status payload, financial amount, signed/download URL,
  token, PEM, or secret in any note, the evidence preview, the proof, or the run record (output-fence
  + no-raw tests + both no-writeback proofs).
- Weak/model/sensitive items shown as review-required, never presented as authoritative; nothing
  auto-promoted.
- Advisory only — no final legal/contractual/claim/safety/financial determination.
- Readiness not overstated; no stop condition triggered.

## Handoff

- **Changed:** new `obsidian/cross_source` renderer + `__init__`, 3 run-record store methods,
  `cross-source` CLI sub-app, new obsidian test file, `docs/architecture/54-…md`, this evidence (+
  committed dry-run preview/proof), README 07D ledger.
- **Gates pass/fail:** unchanged and honest (`meeting_prep_readiness_claim="ready"`); no new gate.
- **Next prompt allowed to proceed:** yes. Prompt 12 (07D gates wiring / no-writeback proof command,
  per the 07D package) may wire the `phase_07d_data_quality_gates` contract and a 07D no-writeback
  proof over the now-complete substrate + outputs.
