# 132 — Phase 09 Prompt 13: LlamaIndex Dependency and Config Surface

**Status:** Implementation — optional dependency + read-only config/status surface (no retrieval runtime built).
**Schema:** V38 (unchanged). **Version:** 1.3.0. **HEAD (audited):** `23e6d87` (worked at `e7c56db`, Prompt 12 closeout).
**Evidence:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/13-llamaindex-dependency-and-config-surface.md` (+ `.json`, `validation-outputs-prompt-13/`).
**Builds on:** record 131 (Prompt 12 V38 schema); the optional-`mcp`-SDK lazy-import pattern (`mcp/policy.py`, `mcp/server.py`); the corpus-balance seed loader + 08x JSON contract loaders.

---

## 1. Purpose

Phase 09's semantic-retrieval plane is built on LlamaIndex. The dependency must be **optional and
lazy-imported** so the local-first base install and the full test suite run with it absent. Prompt 13
declares the optional extra and exposes a read-only config/status surface that reports SDK availability,
the resolved metadata-only config + its `config_hash`, and schema readiness — without importing
LlamaIndex, building an index, or computing any embedding.

## 2. Design

### Optional extra, lazy import
A `retrieval` extra (`llama-index-core`) and a `retrieval-local` extra (adds a local HuggingFace
embedding integration) are declared in `pyproject.toml`, mirroring the `mcp` extra. Nothing imports
LlamaIndex at module load: SDK presence is probed with `importlib.util.find_spec("llama_index")`
(import-free, wrapped against `ImportError`/`ValueError`), and the version via `importlib.metadata`.
SDK-absent is the expected state and is reported, not failed — the same SDK-state-aware posture used for
the optional `mcp` SDK.

### Contract + seed split
A JSON **contract** (`phase_09_llamaindex_config_contract.json`) defines allowed values + posture; a
YAML **seed** (`phase_09_llamaindex_config.seed.yaml`) holds the resolved, metadata-only config values.
`build_llamaindex_config_status` loads both fail-closed (`LlamaIndexConfigError`), validates the config
against the contract (required fields; provider/index/vector kinds in the allowed sets; a deferred
external provider is flagged invalid), and computes a stable `config_hash` (sha256 of the canonical
sorted-key config). The config aligns to the V38
`second_brain_retrieval_llamaindex_config_snapshots` columns (`config_hash`, `embedding_model_label`,
`index_kind`) so later prompts can persist a snapshot without reshaping.

### Read-only status, no writes
The status helper opens the DB `mode=ro`, reads the schema version + snapshot-table presence + row
count, and persists nothing (`ready_to_index = sdk_available and config_valid and schema_ready`;
`blockers` enumerate the gaps). The operator DB stays pristine. The CLI lives at a new two-level Typer
group `second-brain retrieval llamaindex status` (the file's first nested sub-app), exit 0 when the
contract/seed load + config valid + schema ready, else 3.

## 3. Verification

Live (SDK absent): `status` → `sdk.available=false`, `config_valid=true`, `schema_ready=true`,
`ready_to_index=false`, blockers `["llama_index_not_installed"]`, exit 0; operator snapshot table 0 rows.
Full matrix: compileall/ruff clean, mypy 282 files, pytest **3080 passed** (3069 + 11 new),
`construction-agent validate` 4/4 V38, table-inventory 190 / 0 unmapped, 08A/08B/MCP gates +
no-raw/no-writeback proofs pass. `phase-08c-gates` skipped (mutating ledger). LlamaIndex is **not**
installed — the suite proves the lazy-import / SDK-absent paths.

## 4. Guardrails & stop conditions

Optional extra (not installed); lazy import only; read-only over the DB, persists nothing; metadata-only
config (labels + bounded numbers; no raw content / URL / path / token); external embedding providers
deferred and flagged invalid if selected; no embeddings / vector index / semantic retrieval built. No
stop condition triggered.

## LlamaIndex readiness truthful across installs (post-Prompt 19/20 follow-up)

**Follow-up to this prompt (after Prompts 18/19/20 landed).** The original design declared both `retrieval`
(`llama-index-core`) and `retrieval-local` (adds HF) extras (see §2 and pyproject), and the probe was
import-free `find_spec("llama_index")`. Status reported a flat `sdk.available` + `ready_to_index = sdk_available and config_valid and schema_ready`.

This follow-up makes readiness **truthful and easy to validate across base / retrieval / retrieval-local**
installs:

- Split probes: `_llama_index_core_available()` (for `retrieval`; powers status/dry-run) and
  `_local_embedding_available()` (find_spec on the HF submodule; for `retrieval-local`).
- New helper `_embedding_provider_runtime_ready(provider)`: "local" requires core+local; "mock" requires
  only core.
- Status surface expanded (additive): `sdk` dict now includes `core_available`/`core_version`/`local_embedding_available`/`local_embedding_package`/`local_embedding_version` (compat `available`/`version` kept as core); top-level `core_available`, `local_embedding_available`, `local_embedding_package`, `embedding_runtime_ready`.
- `ready_to_index` recomputed as `core and config_valid and schema_ready and embedding_runtime_ready`.
- Blockers now include `local_embedding_not_ready` (when provider=local and HF absent; core absent still
  emits the original `llama_index_not_installed`).
- Install hint remains `pip install -e ".[retrieval]"` (core); docs/runbook clarify `retrieval-local` for
  real apply/semantic.

**Modeled on MCP truthful readiness precedent (this file's sibling record 121).** See record 121 §3:
> **Gap.** Four tests asserted the **SDK-absent** posture unconditionally: ... `assert status["ready_to_serve"] is False` ...
> These were written ... before Prompt 15 ... installed the optional `mcp` SDK and made `ready_to_serve`
> truthful (`policy.py:188,213-215` — `find_spec("mcp")` → `ready_to_serve = foundation_ok and not serve_blockers`).
> ...
> **Resolution (tests only).** The four tests now assert SDK-state-aware: ... SDK present → `ready_to_serve=True` / `serve_blockers=[]`; absent → `False` / `["mcp_sdk_not_installed"]`.

We replicated the pattern for LlamaIndex: renamed probes for clarity, added local probe + runtime gate,
split the apply gate (core → `sdk_not_available`; local-missing on default → `local_embedding_not_ready`),
wrapped the unguarded HF imports in vector writer + hybrid _semantic_query with proper blocker returns,
updated all plan/status/hybrid returns + CLI humans + docstrings, and made tests branch on both states
(renamed 3 monkeypatch sites; extended vector apply gate test with core-true + local-false case asserting
the new blocker).

**No change to contract/seed/schema** (additive fields only; V38 unchanged). External providers remain
deferred (per contract).

**Verification (per plan):** `llamaindex status`/`build`/`build-proof` (base, no extras — core=false,
local=false, ready=false, appropriate blockers, exit 0 for dry surfaces); after `pip install -e ".[retrieval]"`
(core present, local absent) re-run status (core=true, local=false, ready=false, local_embedding_not_ready
in blockers for default provider), `build-apply-proof` passes (Mock, core only), `build --apply` blocks
with `local_embedding_not_ready`; targeted ruff/mypy/pytest on the surfaces + `construction-agent validate`;
hybrid status reflects local + new blocker. All guardrails (lazy, base-clean, fail-closed, metadata-only,
Mock-in-proofs, deferred externals, no SQLite vectors) preserved; final commit emits only the manifest
summary+body.

See also updates in 120 (rebaseline), 121 (MCP precedent), 131 (schema), 133 (embedding policy), 137
(dry-run), 138 (apply), 139 (hybrid), runbook, and 00-README.
