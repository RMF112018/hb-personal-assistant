# 54 — Phase 07D: Obsidian Cross-Source Intelligence Outputs

**Status:** Implemented (Phase 07D Prompt 11). Additive over schema **V25** (no migration).
**Scope:** Project the six 07D read models into **marker-bounded Obsidian notes without raw content**,
via a new `construction-agent cross-source obsidian/status` sub-app, mirroring the Phase 07A
`data-quality obsidian` and 07C `document-obsidian` renderers. Dry-run default (repo evidence preview
+ proof, no vault); `--apply` writes marker-bounded vault notes. Run records persist into the V25
`cross_source_intelligence_obsidian_runs` audit table.

## Design

### Engine — `construction/obsidian/cross_source.py`

`ObsidianCrossSourceRenderer(store)`. `render(*, dry_run=True, apply=False, project_filter=None,
evidence_dir=None, vault_root=None, now_utc=None)` returns `{command, mode, ok, schema_version,
repo_sha, generated_utc, project_filter, status, notes_planned, notes_written, review_required_count,
applied_to_vault, vault_paths, evidence_preview_path, rendered_excerpts, stop_conditions_checked,
guardrails}`.

**Source = the six 07D read-model `*_status()` summaries** (`relationship_substrate_status`,
`meeting_prep_brief_status`, `project_issue_history_status`, `project_risk_digest_status`,
`project_aging_exposure_status`, `correspondence_context_status`), each of which emits **safe
aggregates only** (counts / enums / bands / review counts) — so no raw body / document text / status
payload / token / URL can reach a note. Six marker-bounded sections are rendered
(`HB-CROSS-SOURCE-<KIND>:START/END`), each carrying an advisory callout with the review-required
count, the aggregate fields, and a source-traceability line.

**Output-fence:** every rendered section (and final note) passes `_assert_output_fence`, which rejects
forbidden markers (deltatoken/token/sig/downloadurl/authorization/bearer/access_token/refresh_token/
client_secret/http(s)/PEM/full_document_text/full_body).

**Dry-run (default):** writes `11-obsidian-cross-source-output-preview.md` + a proof JSON to
`evidence_dir` (default `PathPolicy().resolve_repo_root()/docs/evidence/<07d folder>`); no vault write;
`notes_written=0`. **Apply:** writes the six notes under
`vault_root (or ConstructionVaultWriter root) / "Construction Intelligence" / "Phase 07D Cross-Source
Intelligence"` via ensure-markers → replace-bounded → atomic-write, preserving user content (and
frontmatter) outside the markers; degrades gracefully (`applied_to_vault=False`) when no vault is
configured — never raises. `evidence_dir`/`vault_root`/`now_utc` are injectable for tests.

**Run record:** persisted to `cross_source_intelligence_obsidian_runs` (idempotent on
`obsidian_run_id = hash_value("cross_source_obsidian|{project}|{mode}")`), carrying only
`mode`/`output_kind`/`notes_written`/`review_required_count`/`status` — no raw content; guard columns
untouched. `cross_source_obsidian_status()` is a read-only coverage report over the runs table.

### Store — `construction/store/repositories.py`

`upsert/list/count_cross_source_intelligence_obsidian_run(s)`.

### CLI — `construction-agent cross-source`

`obsidian` (`--dry-run`/`--apply` mutually exclusive, default dry-run; `--project`; `--json`) and
`status` (`--project`, `--json`).

### Operational note

Live validation runs **dry-run only**; `--apply` would write the operator's real Obsidian vault (an
outward side effect) and is left for explicit operator action — the apply path is covered by unit
tests against a temp vault, consistent with the 07A/07C precedent (real vault left unwritten).

## Guardrails

Local-first, read-only against external systems; vault write only on `--apply`. No raw email/document/
calendar content, status payload, financial amount, signed/download URL, token, or secret in any note,
the evidence preview, the proof JSON, or the run record (status summaries are already redacted +
output-fence enforced). Advisory only — review-required items are never presented as authoritative;
nothing is auto-promoted.

## Validation

ruff / `mypy src` (189 files) / compileall clean; pytest **+7 new tests**. Live `cross-source obsidian
--dry-run` rendered the six sections and wrote the repo evidence preview (no vault); `cross-source
status` reflects the run record. Both no-writeback proofs pass; `table-inventory` 25 / 120;
`meeting_prep_readiness_claim=ready` unchanged.

## Files

- `src/hb_assistant/construction/obsidian/__init__.py`, `…/cross_source.py` (new).
- `src/hb_assistant/construction/store/repositories.py` (+3 run-record methods).
- `src/hb_assistant/cli/construction.py` (`cross-source` sub-app).
- `tests/test_cross_source_obsidian.py` (new).

See `docs/evidence/construction-intelligence-phase-07d-cross-source-meeting-prep/11-obsidian-cross-source-intelligence-outputs.md`.
