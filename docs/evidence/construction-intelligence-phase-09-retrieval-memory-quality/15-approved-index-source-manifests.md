# Phase 09 Prompt 15 — Approved Index Source Manifests

**Evidence artifact:** `phase_09_approved_index_source_manifests` · **Companion JSON:** `15-approved-index-source-manifests.json`
**No-raw proof companions:** `approved-source-manifest-proof.json` (+ `.md`).
**Classification:** Phase 09 implementation — approved source manifest builder + approval/no-raw guardrail + proof (builds on Prompt 14 no-raw primitives and the V38 substrate).
**Schema:** V38 (unchanged). **Version:** 1.3.0.
**Posture:** metadata-only, local-only, read-only (dry-run by default), fail-closed. **No embeddings computed and no index built.**
**Builds on:** records 131 (V38) + 132 (LlamaIndex config) + 133 (embedding policy); reuses the shared `_FORBIDDEN` scanner, `_assert_no_raw`, `reasoning.FORBIDDEN_REFERENCE_FIELDS`, `retrieval/policy.EXCLUDED_FAMILIES`.

---

## 1. Purpose

The semantic-retrieval plane may index only **approved, redacted, source-linked** records. Per
architecture doc 05 layer 1, an **approved source manifest** enumerates which records from three
categories — generated outputs, approved Obsidian outputs, reviewed memory — are eligible for indexing.
This manifest is the gate the vector-index build (Prompts 18–19) reads. Prompt 15 delivers the manifest
contract + seed, a read-only fail-closed builder + approval/no-raw guardrail, a dry-run-default CLI
build + proof, tests, and evidence. No embeddings computed, no index built.

Stop conditions honored: **unresolved high-impact review items never enter the manifest** (tier-3 /
`review_required` with status ≠ accepted are excluded); **unapproved Obsidian notes are never indexed**
(only the latest `mode='apply'` manifest's entries are eligible); no raw content / writeback / external
calls; review tier / confidence / source refs / freshness preserved as required entry metadata.

## 2. What changed

### Manifest contract + seed
- `src/hb_assistant/resources/json/phase_09_approved_source_manifest_contract.json` — the three
  `manifest_categories` → source families (`second_brain_research_packets` /
  `approved_obsidian_generated_outputs` / `accepted_long_term_memory`), `approved_review_statuses`
  (`accepted`,`auto_advisory`,`review_recommended`), `excluded_review_statuses`
  (`review_required`,`pending_review`,`rejected`,`superseded`), `max_auto_approval_review_tier` (2),
  `required_entry_metadata`, `forbidden_entry_fields`, and global requirements (source-linked-only,
  redacted-only, no-raw, no-writeback, exclude-unresolved-high-impact,
  only-approved-obsidian-apply-manifests, metadata-only, fail-closed).
- `resources/config/phase_09_approved_source_manifest.seed.yaml` — `enabled_categories` (the 3) +
  `max_refs_per_category` (bounded enumeration). No raw/paths/URLs.
- `contracts.py` — registered `approved_source_manifest_contract` in `PHASE_09_CONTRACT_FILES`.

### Builder + guardrail (`retrieval/source_manifest.py`)
- `validate_manifest_entry(entry, *, contract)` — the fail-closed approval + no-raw guardrail: flags
  excluded family, excluded/unapproved review status, `unresolved_high_impact`, missing required
  metadata, forbidden raw fields, and raw/secret/URL shapes (via the shared `_FORBIDDEN` +
  `FORBIDDEN_REFERENCE_FIELDS` + `EXCLUDED_FAMILIES`). Empty ⇒ approved.
- `build_approved_source_manifest(db_path, *, project_key)` — read-only (`mode=ro`): fail-closed schema
  check (≥38 + manifest table present); bounded reads of the three categories (research packets
  accepted; latest apply-mode Obsidian entries; accepted memory) → metadata-only candidates →
  partitioned approved/excluded via the guardrail → per-family counts + a deterministic `manifest_hash`
  over sorted `family:source_ref_hash:content_hash` + review-tier summary + status + warnings.
- `persist_approved_source_manifest(db_path, manifest, *, policy_version)` — INSERTs a single
  guard-clean summary row (counts + hash + tier summary + status; all 23 guards 0). Used by `--apply`
  and the persistence test — **not** run against the operator DB.
- `build_approved_source_manifest_proof(write_evidence)` — runs the guardrail over a safe entry per
  category + 7 planted-unsafe entries; writes a guard-clean JSON+MD companion (`_assert_no_raw` before
  write). Synthetic raw shapes assembled at runtime (no literal tokens in source).

### CLI
- New nested `second-brain retrieval approved-sources` group with `build` (`--dry-run/--apply`,
  `--project`) and `proof` (`--evidence/--no-evidence`). Dry-run default; both read-only over the DB.

## 3. Key results (live)

- `approved-sources build` (operator DB, dry-run): **status `empty`**, `approved_ref_count=0` — the
  operator sources are empty (0 research packets / 0 apply-Obsidian entries / 0 accepted memory), so the
  manifest is honestly empty with `no_approved_sources` + per-family `empty_family:*` warnings. Exit 0.
- `approved-sources proof`: **`proof_passed=true`, 10 cases** — the 3 safe entries (one per category)
  are approved; all 7 planted-unsafe entries (excluded family, rejected/pending status, unresolved
  high-impact, missing metadata, forbidden field, raw shape) are excluded. Guard-clean JSON+MD written.
- Persistence (proof-DB test): a proof DB with one accepted memory → manifest `approved_ref_count=1`
  (`reviewed_memory`); `persist_...` writes one guard-clean summary row (all guards 0).
- Operator DB: schema **38**; `approved_source_manifests` remains **0 rows** (build is read-only/dry-run;
  no `--apply`).

## 4. Validation

`compileall` exit 0 · `ruff check .` clean · `mypy src` clean (**284** source files) ·
`pytest -m "not live and not integration and not manual"` → **3101 passed / 0 failed / 1 deselected**
(prior 3091 + 10 new) · `construction-agent validate` 4/4 schema **V38** · `table-inventory` 190 / 0
unmapped · `no-writeback-proof` `proof_passed=true` · `phase-08a-gates`/`phase-08b-gates` ok ·
`mcp no-raw-access`/`mcp no-writeback` `proof_passed=true` · `retrieval approved-sources build`/`proof`
exit 0. `phase-08c-gates` deliberately skipped (mutating append-only ledger — disclosed Prompts 02/05).
Captures under `validation-outputs-prompt-15/`.

The 10 new tests cover: normal build + guard-clean persist; missing-contract + missing-seed fail-closed;
stale-schema fail-closed; operator-empty-and-honest; every unsafe candidate excluded; proof passes + is
clean; proof writes guard-clean artifacts; build/proof do not mutate the DB; CLI exit codes.

## 5. Guardrails & stop conditions

Metadata-only (counts + hashes; per-entry refs hashed, never stored raw); read-only by default
(`mode=ro`); persistence opt-in and limited to a single guard-clean summary row (not run on the
operator DB); unresolved high-impact / non-accepted / non-apply-Obsidian / raw-content entries
excluded; no embeddings / index built; no external writeback; review tier / confidence / source refs /
freshness preserved. No stop condition triggered.

## 6. Deferred / owning prompts

Vector index build (dry-run/apply) — Prompts 18–19 (will intersect manifest ∩ embedding policy). The
evaluation-run generated-output category is deferred (research packets are the canonical generated
output). Manifest persistence to the operator DB is deferred (`--apply` not run; operator stays
pristine).
