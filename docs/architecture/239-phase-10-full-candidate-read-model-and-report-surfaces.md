# 239 — Phase 10 full-candidate read-model & report surfaces

Records the durable architecture established by the Phase 10 full-candidate implementation
(`experiment/phase-10-full-candidate-implementation`, baseline `0c75f4a7`). Evidence:
`docs/evidence/phase-10-full-candidate-implementation/`.

## The pattern: read-only operator read-model / report surfaces

Most Phase 10 candidates converged on one repeatable surface shape rather than new persistence. A
**read-model / report surface** is a pure builder + a markdown renderer + a thin Typer verb that:

- **composes existing builders/stores** — it never introduces a second contradictory data path;
- is **read-only / dry-run** — it persists nothing and promotes nothing;
- groups data by **operator action / category** with **deterministic, enum-driven** logic (no model
  decides grouping);
- is **source-linked** (ids / hashed refs) and **raw-free** (no bodies / prompts / responses / URLs /
  tokens / email dumps — counts, hashes, enums, short labels only);
- **degrades honestly / fails closed** on missing data, unavailable model, or forbidden content;
- emits **JSON by default**, Markdown via `--no-json` / `--markdown-out`, with a `guardrails` block.

## Surfaces added

| Module (`construction/second_brain/local_ai/…` unless noted) | CLI verb | Role |
|---|---|---|
| `daily_run.py` / `daily_run_html.py` | `second-brain daily-run run` | V45 pending-followup section converged onto browser HTML + Obsidian + status; status gains an operator-legible `run_summary` block |
| `candidate_review.py` (`build_review_report`) | `second-brain review report` | candidate lifecycle report (pending/accepted/rejected/needs-review + bounded preview-apply) |
| `follow_up_watch.py` (`build_follow_up_watch_report`) | `second-brain follow-up-watch report` | accepted-item watch grouped by operator action + quality gates |
| `model_diagnostics.py` | `second-brain local-model diagnostics` | routing diagnostics across all task families (profile/chain/probe/fallback/fail-closed/safety) |
| `procore_monitor.py` | `procore live monitor` | endpoint contract + per-project refresh health + degraded-honest verdict |
| `relationship_entity_report.py` | `second-brain relationship-candidates report` | V25 cross-source candidates grouped by operator category |
| `mcp_packet_hardening.py` | `second-brain daily-brief mcp-packet` | MCP packet contract envelope + fail-closed forbidden-content gate over the context packet |
| `file_parse_read_model.py` | `hb-assistant files parse-index` | review-safe file parse read-model (metadata + content hash, never the extracted text) |

## Two durable contracts introduced

- **Daily-run `run_summary`** (`daily_run.py:_build_run_summary`): one redacted, operator-legible
  status block — result (incl. explicit `degraded`), wall-clock started/completed, output +
  last-successful paths, per-stage receipts, safe error summary, `browser_auto_opened: false`.
- **MCP packet contract** (`mcp_packet_hardening.py`, `phase10-mcp-1.0`): purpose, generated_at,
  source window, candidate summaries, source-ref summary, caps applied, **omitted-raw categories**,
  redaction flags, freshness warnings — plus a regex forbidden-content gate that scans the real
  payload (not the contract labels) and withholds the context on any match.

## Invariants (enforced in code + per-candidate evidence)

No schema migration was added (schema stays at V45). No external writeback, no cloud LLM, no raw
content. Guard columns on touched tables stay zero. The production DB is never mutated — every
candidate validates on disposable temp copies and proves the production sha256 unchanged.

## Post-merge hardening (branch `fix/phase-10-postmerge-hardening`)

After PR #13 merged this work to `main` (merge commit `483e090d`), a focused hardening pass tightened
three contracts above without changing schema or behavior shape. Evidence:
`docs/evidence/phase-10-postmerge-hardening/`.

- **Operator Markdown is reachable on every surface.** `files parse-index` and
  `daily-brief mcp-packet` declared only `--json`; both already rendered Markdown in their `else`
  branch, so the fix is the paired `--json/--no-json` flag only. The whole surface family now
  honors the "JSON by default, Markdown via `--no-json`/`--markdown-out`" contract uniformly.
- **Follow-up watch persistence is quality-gated.** `run_follow_up_watch_scan` previously gated
  persistence on source refs alone, so a source-linked but **contradictory** item (terminal status +
  active waiting_state + no completion) could persist as actionable even though
  `build_follow_up_watch_report` routes it to `needs_review`. The scan now applies the same
  `watch_quality_flags(...)` and refuses to persist any flagged item (`skipped_quality_flags`
  counter; `quality_flags` + `skipped_reason="quality_flags"` on the entry; `quality_gated`
  guardrail). The report and the persist path now agree. No schema change.
- **File-parse hash scope is explicit.** `file_parse_read_model` hashed the parser's **bounded**
  `text_excerpt` (parsers cap the excerpt — e.g. `text[:max_chars]`, PDF first N pages) but emitted
  it as `text_hash`, implying a full-text hash. The field is renamed to `text_excerpt_hash` with an
  explicit `hash_scope: "text_excerpt"` (no alias; Markdown shows `excerpt-hash:`). `text_length`
  is likewise the excerpt length. Downstream-consumer grep confirms nothing depended on the old
  field; the unrelated `text_hash` in Procore enrichment/history is a different symbol.
