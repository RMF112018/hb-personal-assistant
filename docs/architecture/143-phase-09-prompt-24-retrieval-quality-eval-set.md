# 143 — Phase 09 Prompt 24: Retrieval Quality Eval Set

**Status:** Implementation — source-linked retrieval eval cases from approved outputs; read-only, fail-closed, metadata-only.
**Schema:** V38 (unchanged; reuses `eval_sets` + `eval_cases`). **Version:** 1.4.0-phase-09. **HEAD (audited):** `23e6d87` (worked at `2e0a783`, Prompt 23 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/24-retrieval-quality-eval-set.md` (+ `.json`, `retrieval-eval-set-proof.{json,md}`, `validation-outputs-prompt-24/`).
**Builds on:** records 134–142; reuses `vector_index._gather_approved_nodes` (the approved Obsidian + reviewed-memory loaders), `ALLOWLISTED_SOURCE_FAMILIES`/`EXCLUDED_FAMILIES` (policy), and `_assert_no_raw`.

---

## 1. Purpose

Create the **retrieval quality eval set**: source-linked retrieval evaluation cases derived from the
**approved outputs** corpus. Each case asserts "a query targeting this approved output should retrieve this
source," linked only by a hashed ref. The cases are the fixtures a later prompt will execute/score against
the index (`eval_runs`); this prompt builds them.

## 2. Design

### Approved outputs are the only source
`_gather_approved_nodes(db_path, project_key)` (reused from `vector_index`) enumerates the approved
Obsidian generated outputs + reviewed/accepted long-term memory — already validated by the loaders. The
manifest only exposes counts, so the loaders are the per-entry source of truth.

### One source-linked case per approved node
`_build_cases` admits a node iff it carries a `source_ref` + an allowlisted (non-`EXCLUDED`)
`source_family`; unsafe/unlinked/excluded nodes are skipped. Each case stores `eval_case_id =
hash(set_id:family:source_ref)`, `expected_source_ref_hash = hash(source_ref)` (hashed — never the raw
ref), `question_hash = hash(family:source_ref:retrieval)` (a deterministic query *seed* hash — no raw
query text is created or stored), and `confidence_class`. The eval set carries `eval_set_id =
res_<set_hash[:32]>`, a hashed `name_hash`, `case_count`, a `review_tier` summary, and `status`
(`built`/`empty`).

### Read-only, metadata-only, fail-closed
`build_retrieval_eval_set` defaults `emit_receipt=False` (persists nothing); `persist_retrieval_eval_set`
writes the `eval_sets` + `eval_cases` rows (metadata-only, all 23 `CHECK(=0)` guards 0), mirroring the
`vector_index` persister pattern, exercised in the proof on a temp DB. No raw content/query/answer/source
ref is emitted (only hashes). Fail-closed on missing policy or stale schema (V38-gated). No embeddings are
involved — the eval set is pure metadata enumeration.

## 3. Contract & seed

`phase_09_retrieval_eval_set_contract.json` (+ `.seed.yaml`): approved-outputs source families, eval_set /
eval_case column allowlists, forbidden-emitted fields (raw query/content/answer/source_ref), status vocab,
`max_cases_per_set`, and global requirements (preserve review tier/confidence/source refs/freshness;
source-linked cases only; approved outputs only; fail-closed). Registered as `retrieval_eval_set_contract`.

## 4. CLI

`second-brain retrieval eval-set build [--project] [--name NAME] | proof`. Unique Typer var / guardrails
constant / command names. `build` is read-only (no persist; on the operator DB it is honestly `empty`);
`proof` runs the offline guard-clean proof.

## 5. Validation

`compileall`/`ruff`/`mypy` (292 files) clean; `pytest -m "not live and not integration and not manual"`
= 3173 passed, 0 failed. The eval-set proof passes (3 source-linked cases from approved outputs;
guard-clean metadata-only `eval_sets` + `eval_cases` receipts; unsafe/unlinked/excluded node excluded; no
raw source ref emitted). Operator DB unmutated (both tables 0; schema 38). Full matrix in the evidence bundle.

## 6. Deferred

Executing/scoring the eval set against the index (`eval_runs` + pass/fail) — a later prompt; the
`generated_outputs` loader (cases derive from Obsidian + reviewed memory); benchmarks / memory-quality
review — later Phase 09 prompts.
