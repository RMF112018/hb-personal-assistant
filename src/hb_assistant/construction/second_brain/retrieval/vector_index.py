"""Phase 09 Prompts 18–19 — vector index build (read-only dry run + policy-gated apply, fail-closed).

The **dry run** (Prompt 18) produces a metadata-only **build plan** over the approved source manifest's
nodes — what *would* be embedded and indexed — computing no embeddings and writing no vector store.

The **apply** (Prompt 19) embeds those approved nodes via LlamaIndex and writes a vector store **on the
local filesystem under Application Support — never to SQLite**, persisting metadata-only receipts (one
`status='applied'` `vector_index_runs` row + one `vector_index_items` row per node). Apply is gated: it
fails closed (`status='apply_blocked'`) when the optional LlamaIndex core SDK is absent
(`sdk_not_available`), when the local embedding backend required for the default provider is absent
(`local_embedding_not_ready`), when there are no indexable nodes, or when policy/schema is not ready —
persisting nothing in those cases. `build --apply` requires `pip install -e ".[retrieval-local]"` (core
+ local HF); `build-apply-proof` and dry-run/build-proof run with only `[retrieval]` (core) via injected
`MockEmbedding`.

The **approved source manifest is the only input** (provenance + authorization), and the node sources
are the per-category loaders (Obsidian + reviewed memory), which already enforce approved + source-linked
+ guard-clean. Both paths re-assert the build rule on every node: **reject any source lacking review
tier, confidence, source ref, or freshness metadata, or failing the no-raw proof** (Prompt 14's
`validate_embedding_candidate`). The third manifest category (generated outputs) is now served by the
generated-outputs loader (accepted research packets + applied source-linked daily briefs); only manifest-eligible
records become nodes and the deferred warning is suppressed when eligible generated nodes are present.

Everything is metadata-only (counts + hashes; no node text, no vectors persisted to SQLite) and
fail-closed. The embedder/vector-store writer is injectable: the default is a LlamaIndex
`VectorStoreIndex` + `SimpleVectorStore` backed by the configured local embedding model; proofs/tests
inject a deterministic `MockEmbedding`-backed writer so the default-safe suite runs fully offline.

Public entry points:
  build_vector_index_dry_run(db_path=None, *, project_key=None) -> dict
  persist_dry_run_record(db_path, plan, *, policy_version) -> str
  build_vector_index_dry_run_proof(*, evidence_dir=None, write_evidence=True) -> dict
  build_vector_index_apply(db_path=None, *, project_key=None, writer=None, persist_root=None) -> dict
  persist_apply_record(db_path, receipt, *, policy_version) -> str
  build_vector_index_apply_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain retrieval llamaindex build [--dry-run|--apply] | build-proof
     | build-apply-proof --json
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import subprocess
import tempfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from hb_assistant.config.path_policy import PathPolicy

from ..contracts import load_phase_09_contract
from ..financial_review_routing import _assert_no_raw
from .embedding_policy import (
    load_embedding_vector_policy_contract,
    load_embedding_vector_policy_seed,
    validate_embedding_candidate,
)
from .generated_outputs_loader import load_approved_generated_output_nodes
from .llamaindex_config import (
    _llama_index_core_available,
    _local_embedding_available,
    load_llamaindex_config_seed,
)
from .memory_loader import load_reviewed_memory_nodes
from .obsidian_loader import load_approved_obsidian_nodes
from .source_manifest import build_approved_source_manifest

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "vector-index-dry-run-proof.json"
_PROOF_MD = "vector-index-dry-run-proof.md"
_APPLY_PROOF_JSON = "vector-index-apply-proof.json"
_APPLY_PROOF_MD = "vector-index-apply-proof.md"

_RUNS_TABLE = "second_brain_retrieval_vector_index_runs"
_ITEMS_TABLE = "second_brain_retrieval_vector_index_items"
_REQUIRED_FIELDS = ("review_tier", "confidence_class", "source_ref", "freshness_label")

_APPLY_SEED_RELATIVE = Path("resources") / "config" / "phase_09_vector_index_apply.seed.yaml"

# A vector-store writer embeds the approved nodes and persists the store to `persist_dir` (outside
# SQLite), returning a metadata-only receipt: written_count, embedding_dim, vector_store_kind, and a
# {node_id: chunk_count} map. The default is LlamaIndex-backed using the local HF embedder (requires
# both `retrieval` and `retrieval-local` extras for the real --apply path); proofs/tests inject a
# MockEmbedding (core only, via `[retrieval]`) to keep the default-safe suite offline.
VectorStoreWriter = Callable[..., dict[str, Any]]


class VectorIndexBuildError(RuntimeError):
    """Raised when the vector-index build cannot resolve policy/schema (fail-closed)."""


def load_vector_index_apply_contract() -> dict[str, Any]:
    """Load the vector-index apply contract (fail-closed if missing/invalid)."""
    contract = load_phase_09_contract("vector_index_apply_contract")
    if not isinstance(contract, dict) or "allowed_status_values" not in contract:
        raise VectorIndexBuildError(
            "phase 09 vector-index apply contract not found or missing required fields"
        )
    return contract


def load_vector_index_apply_seed() -> dict[str, Any]:
    """Load the resolved vector-index apply seed (fail-closed if missing/invalid)."""
    candidate = PathPolicy().resolve_repo_root() / _APPLY_SEED_RELATIVE
    if not candidate.exists():
        raise VectorIndexBuildError(f"vector-index apply seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "status_values" not in data:
        raise VectorIndexBuildError(f"{candidate} must define the vector-index apply policy")
    return data


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_sha() -> str:
    try:
        repo_root = Path(__file__).resolve().parents[5]
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _open_ro(db_path: str | None) -> sqlite3.Connection | None:
    resolved = db_path or str(PathPolicy().get_db_path())
    try:
        return sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _schema_ready(db_path: str | None) -> int:
    """Return the schema version if ready (>=38 with the runs table), else raise fail-closed."""
    conn = _open_ro(db_path)
    if conn is None or not _table_exists(conn, "schema_migrations"):
        if conn is not None:
            conn.close()
        raise VectorIndexBuildError(
            "schema not ready for vector-index build (no schema_migrations)"
        )
    try:
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        if version < 38 or not _table_exists(conn, _RUNS_TABLE):
            raise VectorIndexBuildError(
                f"schema not ready for vector-index build (version {version}, expected >= 38)"
            )
    finally:
        conn.close()
    return version


def _apply_build_rule(
    node: dict[str, Any], *, contract: dict[str, Any], seed: dict[str, Any]
) -> list[str]:
    """Return build-rejection reasons for a node (empty ⇒ indexable). Fail-closed.

    Rejects any node lacking review tier / confidence / source ref / freshness metadata, or failing the
    embedding no-raw guardrail (the no-raw proof).
    """
    violations = [f"missing_{f}" for f in _REQUIRED_FIELDS if node.get(f) in (None, "")]
    violations.extend(validate_embedding_candidate(node, contract=contract, seed=seed))
    return violations


def _gather_approved_nodes(
    db_path: str | None, project_key: str | None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Gather approved nodes from all manifest-eligible categories (Obsidian + reviewed memory + generated outputs),
    with the approved source manifest as authorization and provenance. Generated outputs are included only when
    they are manifest-eligible (accepted research packets or apply-mode source-linked daily briefs).
    """
    manifest = build_approved_source_manifest(db_path, project_key=project_key)
    nodes: list[dict[str, Any]] = []
    nodes.extend(load_approved_obsidian_nodes(db_path, project_key=project_key))
    nodes.extend(load_reviewed_memory_nodes(db_path, project_key=project_key))
    nodes.extend(load_approved_generated_output_nodes(db_path, project_key=project_key))
    return nodes, manifest


def _build_plan(
    db_path: str | None, project_key: str | None
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Resolve policy/config, gather approved nodes, apply the build rule (fail-closed).

    Returns ``(plan, indexable_nodes, embedding_contract, embedding_seed, llamaindex_config)``. The plan
    is the read-only dry-run dict (``status='dry_run'``); ``indexable_nodes`` is the in-memory node list
    the apply path embeds (never persisted).

    The plan includes truthful `sdk_available` (core from `retrieval`), `local_embedding_available` (HF
    from `retrieval-local`), and `ready_to_apply` which is true only when both + indexable nodes.
    """
    contract = load_embedding_vector_policy_contract()
    seed = load_embedding_vector_policy_seed()
    config = load_llamaindex_config_seed()
    schema_version = _schema_ready(db_path)

    nodes, manifest = _gather_approved_nodes(db_path, project_key)

    chunk_size = int(config.get("chunk_size", 512)) or 512
    indexable: list[dict[str, Any]] = []
    rejected = 0
    reasons: dict[str, int] = {}
    per_family: dict[str, int] = {}
    planned_chunks = 0
    for node in nodes:
        violations = _apply_build_rule(node, contract=contract, seed=seed)
        if violations:
            rejected += 1
            for v in violations:
                reasons[v.split(":")[0]] = reasons.get(v.split(":")[0], 0) + 1
            continue
        indexable.append(node)
        fam = str(node["source_family"])
        per_family[fam] = per_family.get(fam, 0) + 1
        text_len = len(str(node.get("text_redacted", "")))
        planned_chunks += max(1, math.ceil(text_len / chunk_size))

    core_available = _llama_index_core_available()
    local_embedding_available = _local_embedding_available()
    config_hash = _hash(
        json.dumps({k: config.get(k) for k in sorted(config)}, sort_keys=True, default=str)
    )
    index_plan_hash = _hash(
        "|".join(
            sorted(
                f"{n['source_family']}:{_hash(str(n['source_ref']))[:16]}:{n['content_hash']}"
                for n in indexable
            )
        )
    )
    gen_count = per_family.get("generated_outputs", 0)
    warnings: list[str] = []
    if not indexable:
        warnings.append("no_approved_nodes")
    if gen_count == 0:
        warnings.append("generated_outputs_loader_deferred")

    plan = {
        "command": "second-brain retrieval llamaindex build",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": "dry_run",
        "manifest_id": manifest["manifest_id"],
        "manifest_hash": manifest["manifest_hash"],
        "schema_version": schema_version,
        "embedding_model_label": config.get("embedding_model_label"),
        "index_kind": config.get("index_kind"),
        "vector_store_kind": config.get("vector_store_kind"),
        "config_hash": config_hash,
        "index_plan_hash": index_plan_hash,
        "total_nodes": len(indexable),
        "per_family_node_count": per_family,
        "rejected_node_count": rejected,
        "rejected_reasons": reasons,
        "planned_chunk_count": planned_chunks,
        "sdk_available": core_available,
        "local_embedding_available": local_embedding_available,
        "ready_to_apply": core_available and local_embedding_available and bool(indexable),
        "no_raw_attested": True,
        "vectors_persisted_to_sqlite": False,
        "warnings": warnings,
        "policy_version": seed.get("version"),
        "read_only": True,
    }
    return plan, indexable, contract, seed, config


def build_vector_index_dry_run(
    db_path: str | None = None, *, project_key: str | None = None
) -> dict[str, Any]:
    """Build the read-only dry-run vector-index plan (fail-closed). Persists nothing."""
    plan, _indexable, _contract, _seed, _config = _build_plan(db_path, project_key)
    return plan


def persist_dry_run_record(
    db_path: str | None, plan: dict[str, Any], *, policy_version: str
) -> str:
    """Persist a single guard-clean dry-run `vector_index_runs` row. Proof/test only. Returns run_id."""
    resolved = db_path or str(PathPolicy().get_db_path())
    run_id = f"vir_dryrun_{plan['index_plan_hash'][:32]}"
    conn = sqlite3.connect(resolved)
    try:
        conn.execute(
            f"INSERT OR REPLACE INTO {_RUNS_TABLE} "
            "(run_id, policy_version, schema_version, manifest_id, project_key, item_count, status, "
            "config_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                policy_version,
                int(plan["schema_version"]),
                str(plan["manifest_id"]),
                None,
                int(plan["total_nodes"]),
                "dry_run",
                str(plan["config_hash"]),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return run_id


def _resolve_persist_dir(run_id: str, persist_root: str | None) -> Path:
    """Resolve the vector-store directory (outside SQLite, under Application Support by default)."""
    root = (
        Path(persist_root)
        if persist_root
        else PathPolicy().get_app_support() / "retrieval" / "vector_store"
    )
    out = root / run_id
    out.mkdir(parents=True, exist_ok=True)
    return out


def _llamaindex_vector_writer(
    nodes: list[dict[str, Any]],
    *,
    persist_dir: str,
    config: dict[str, Any],
    embed_model: Any | None = None,
) -> dict[str, Any]:
    """Default writer: embed redacted node text via LlamaIndex and persist a SimpleVectorStore to disk.

    Lazy-imports the optional core SDK (fail-closed if absent). If no embed_model is injected, requires
    the local HF embedding backend (from `retrieval-local`) and imports it; proofs/tests always inject
    `MockEmbedding` (from core only) so the default-safe suite and build-apply-proof run with just
    `[retrieval]`. Builds one `Document` per approved node (keyed by `node_id`), embeds, and persists the
    vector store to `persist_dir` (under Application Support, **never to SQLite**). Returns a
    metadata-only receipt (no vectors, no text).
    """
    try:
        from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
        from llama_index.core.vector_stores import SimpleVectorStore
    except ImportError as exc:  # pragma: no cover - exercised via apply gate
        raise VectorIndexBuildError(f"llama-index core not available: {exc}") from exc

    if embed_model is None:
        if not _local_embedding_available():
            raise VectorIndexBuildError(
                "local embedding backend (llama-index-embeddings-huggingface) not available; "
                "install with `pip install -e '.[retrieval-local]'` for the default 'local' provider"
            )
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding

        embed_model = HuggingFaceEmbedding(model_name=str(config.get("embedding_model_label")))

    Settings.embed_model = embed_model
    Settings.chunk_size = int(config.get("chunk_size", 512)) or 512
    Settings.chunk_overlap = int(config.get("chunk_overlap", 0) or 0)

    documents = []
    for node in nodes:
        doc = Document(
            text=str(node.get("text_redacted", "")),
            metadata={"source_family": str(node["source_family"])},
        )
        doc.id_ = str(node["node_id"])
        documents.append(doc)

    storage_context = StorageContext.from_defaults(vector_store=SimpleVectorStore())
    index = VectorStoreIndex.from_documents(
        documents, storage_context=storage_context, show_progress=False
    )
    storage_context.persist(persist_dir=persist_dir)

    chunk_counts: dict[str, int] = {}
    for chunk in index.docstore.docs.values():
        ref = getattr(chunk, "ref_doc_id", None)
        if ref:
            chunk_counts[str(ref)] = chunk_counts.get(str(ref), 0) + 1

    embedding_dim = len(embed_model.get_text_embedding("dimension probe"))
    return {
        "written_count": len(documents),
        "embedding_dim": int(embedding_dim),
        "vector_store_kind": str(config.get("vector_store_kind", "simple")),
        "chunk_counts": chunk_counts,
    }


def _apply_items(
    run_id: str, indexable: list[dict[str, Any]], receipt: dict[str, Any]
) -> list[dict]:
    """Build metadata-only per-node item rows (hashed source ref; never raw text/vectors)."""
    chunk_counts = receipt.get("chunk_counts", {})
    items: list[dict[str, Any]] = []
    for node in indexable:
        node_id = str(node["node_id"])
        items.append(
            {
                "item_id": _hash(f"{run_id}:{node_id}")[:48],
                "source_family": str(node["source_family"]),
                "source_ref_hash": _hash(str(node["source_ref"]))[:48],
                "content_hash": str(node["content_hash"]),
                "confidence_class": str(node["confidence_class"]),
                "freshness_label": str(node["freshness_label"]),
                "chunk_count": int(chunk_counts.get(node_id, 1)),
            }
        )
    return items


def build_vector_index_apply(
    db_path: str | None = None,
    *,
    project_key: str | None = None,
    writer: VectorStoreWriter | None = None,
    persist_root: str | None = None,
) -> dict[str, Any]:
    """Policy-gated apply build: embed approved nodes, write the vector store, persist receipts.

    The approved source manifest is the only input; every node must carry review tier / confidence /
    source ref / freshness metadata and pass the no-raw guardrail (re-asserted here). Vectors are written
    to `persist_root` (default: Application Support) — **never to SQLite**; only metadata-only receipts
    (`vector_index_runs` `status='applied'` + per-node `vector_index_items`) are persisted. Fails closed
    (`status='apply_blocked'`, nothing persisted) when core SDK absent (`sdk_not_available`), local
    embedding backend absent for default writer (`local_embedding_not_ready`), there are no indexable
    nodes, or policy/schema is not ready. Default writer path requires `retrieval-local`; proofs use
    injected writer + MockEmbedding and need only `retrieval`.
    """
    load_vector_index_apply_contract()
    apply_seed = load_vector_index_apply_seed()
    plan, indexable, contract, seed, config = _build_plan(db_path, project_key)
    policy_version = str(seed.get("version"))

    base = {
        "command": "second-brain retrieval llamaindex build --apply",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "manifest_id": plan["manifest_id"],
        "manifest_hash": plan["manifest_hash"],
        "schema_version": plan["schema_version"],
        "config_hash": plan["config_hash"],
        "index_plan_hash": plan["index_plan_hash"],
        "embedding_model_label": config.get("embedding_model_label"),
        "vector_store_kind": config.get("vector_store_kind"),
        "persist_dir_label": config.get("persist_dir_label"),
        "vector_store_location": str(
            apply_seed.get("vector_store_location", "external_filesystem")
        ),
        "vectors_persisted_to_sqlite": False,
        "apply_policy_version": apply_seed.get("version"),
        "policy_version": policy_version,
        "project_key": project_key,
    }

    using_default_writer = writer is None
    if using_default_writer and not _llama_index_core_available():
        return {**base, "status": "apply_blocked", "blocker_reason": "sdk_not_available"}
    if using_default_writer and not _local_embedding_available():
        return {**base, "status": "apply_blocked", "blocker_reason": "local_embedding_not_ready"}
    if not indexable:
        return {**base, "status": "apply_blocked", "blocker_reason": "no_indexable_nodes"}

    # Defense in depth: re-assert the build rule on every node before it is embedded.
    for node in indexable:
        if _apply_build_rule(node, contract=contract, seed=seed):
            return {**base, "status": "apply_blocked", "blocker_reason": "no_indexable_nodes"}

    run_id = f"vir_apply_{plan['index_plan_hash'][:32]}"
    persist_dir = _resolve_persist_dir(run_id, persist_root)
    active_writer = writer or _llamaindex_vector_writer
    receipt = active_writer(indexable, persist_dir=str(persist_dir), config=config)

    items = _apply_items(run_id, indexable, receipt)
    applied = {
        **base,
        "status": "applied",
        "run_id": run_id,
        "total_items": len(items),
        "per_family_item_count": plan["per_family_node_count"],
        "embedding_dim": int(receipt.get("embedding_dim", 0)),
        "vector_files_present": any(persist_dir.iterdir()),
        "warnings": plan["warnings"],
        "items": items,
    }
    persist_apply_record(db_path, applied, policy_version=policy_version)
    return applied


def persist_apply_record(
    db_path: str | None, receipt: dict[str, Any], *, policy_version: str
) -> str:
    """Persist a guard-clean applied run + per-node item rows (metadata-only). Returns run_id."""
    resolved = db_path or str(PathPolicy().get_db_path())
    run_id = str(receipt["run_id"])
    conn = sqlite3.connect(resolved)
    try:
        conn.execute(
            f"INSERT OR REPLACE INTO {_RUNS_TABLE} "
            "(run_id, policy_version, schema_version, manifest_id, project_key, item_count, status, "
            "config_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                policy_version,
                int(receipt["schema_version"]),
                str(receipt["manifest_id"]),
                receipt.get("project_key"),
                int(receipt["total_items"]),
                "applied",
                str(receipt["config_hash"]),
            ),
        )
        for item in receipt["items"]:
            conn.execute(
                f"INSERT OR REPLACE INTO {_ITEMS_TABLE} "
                "(item_id, policy_version, schema_version, run_id, source_family, source_ref_hash, "
                "content_hash, confidence_class, freshness_label, chunk_count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(item["item_id"]),
                    policy_version,
                    int(receipt["schema_version"]),
                    run_id,
                    str(item["source_family"]),
                    str(item["source_ref_hash"]),
                    str(item["content_hash"]),
                    str(item["confidence_class"]),
                    str(item["freshness_label"]),
                    int(item["chunk_count"]),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return run_id


def _proof_db(tmp: str) -> str:
    """Build a proof DB with an apply-mode Obsidian index + one accepted memory item."""

    from ..memory.models import MemoryItem
    from ..memory.store import write_memory_item
    from ..obsidian_index.indexer import build_index
    from ..obsidian_linkage_proof import write_linkage_fixture_vault

    vault = Path(tmp) / "vault"
    write_linkage_fixture_vault(vault)
    db = str(Path(tmp) / "vidx.sqlite")
    build_index(mode="apply", vault_root=vault, db_path=db)
    write_memory_item(
        MemoryItem(
            memory_id="m-proof-1",
            memory_type="fact",
            statement_redacted="[redacted project summary]",
            confidence_class="high",
            review_status="accepted",
            source_refs=[{"source_family": "cross_source_relationships", "source_ref": "rel-1"}],
        ),
        db_path=db,
    )
    return db


def _rule_cases() -> list[dict[str, Any]]:
    """Controlled safe + planted-unsafe nodes exercising the build rule."""
    contract = load_embedding_vector_policy_contract()
    seed = load_embedding_vector_policy_seed()
    safe = {
        "source_family": "accepted_long_term_memory",
        "source_ref": "m-1",
        "content_hash": "f" * 16,
        "confidence_class": "high",
        "review_tier": 1,
        "review_status": "accepted",
        "review_required": False,
        "freshness_label": "current",
        "text_redacted": "[redacted project summary]",
    }
    synthetic_secret = "Bea" + "rer " + "z" * 32
    planted: list[tuple[str, dict[str, Any]]] = [
        ("missing_review_tier", {k: v for k, v in safe.items() if k != "review_tier"}),
        ("missing_confidence", {k: v for k, v in safe.items() if k != "confidence_class"}),
        ("missing_source_ref", {k: v for k, v in safe.items() if k != "source_ref"}),
        ("missing_freshness", {k: v for k, v in safe.items() if k != "freshness_label"}),
        ("raw_shape_text", {**safe, "text_redacted": synthetic_secret}),
        ("non_embeddable_family", {**safe, "source_family": "raw_prompt"}),
    ]
    cases: list[dict[str, Any]] = []
    v = _apply_build_rule(safe, contract=contract, seed=seed)
    cases.append(
        {
            "name": "safe_node",
            "expected_indexable": True,
            "indexable": not v,
            "violations": v,
            "passed": not v,
        }
    )
    for name, node in planted:
        v = _apply_build_rule(node, contract=contract, seed=seed)
        cases.append(
            {
                "name": name,
                "expected_indexable": False,
                "indexable": not v,
                "violations": v,
                "passed": bool(v),
            }
        )
    return cases


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Vector Index Build (Dry Run) Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- proof_total_nodes: {proof['proof_total_nodes']}",
        f"- dry_run_record_persisted: {proof['dry_run_record_persisted']}",
        f"- dry_run_record_guard_clean: {proof['dry_run_record_guard_clean']}",
        f"- vectors_persisted_to_sqlite: {proof['vectors_persisted_to_sqlite']} (must be false)",
        "",
        "## Build-rule cases",
        "",
    ]
    for c in proof["cases"]:
        lines.append(
            f"- [{'ok' if c['passed'] else 'FAIL'}] {c['name']}: "
            f"expected_indexable={c['expected_indexable']} indexable={c['indexable']} "
            f"violations={len(c['violations'])}"
        )
    lines.append("")
    return "\n".join(lines)


def build_vector_index_dry_run_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: dry-run plan + build-rule + guard-clean dry-run record (no operator writes)."""
    with tempfile.TemporaryDirectory() as tmp:
        db = _proof_db(tmp)
        plan = build_vector_index_dry_run(db)
        run_id = persist_dry_run_record(db, plan, policy_version=str(plan["policy_version"]))
        conn = sqlite3.connect(db)
        try:
            row = conn.execute(
                f"SELECT status, item_count, raw_vector_content_persisted, external_writeback_performed "
                f"FROM {_RUNS_TABLE} WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        finally:
            conn.close()
    record_persisted = row is not None and row[0] == "dry_run"
    record_guard_clean = bool(row) and row[2] == 0 and row[3] == 0
    cases = _rule_cases()
    proof_passed = (
        plan["total_nodes"] >= 1
        and plan["vectors_persisted_to_sqlite"] is False
        and record_persisted
        and record_guard_clean
        and all(c["passed"] for c in cases)
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_vector_index_dry_run",
        "command": "second-brain retrieval llamaindex build-proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "proof_total_nodes": plan["total_nodes"],
        "proof_planned_chunk_count": plan["planned_chunk_count"],
        "dry_run_record_persisted": record_persisted,
        "dry_run_record_guard_clean": record_guard_clean,
        "vectors_persisted_to_sqlite": plan["vectors_persisted_to_sqlite"],
        "case_count": len(cases),
        "cases": cases,
        "metadata_only": True,
        "guardrails": {
            "read_only": True,
            "no_raw": True,
            "no_writeback": True,
            "approved_manifest_only_input": True,
            "no_raw_vector_content_in_sqlite": True,
            "dry_run_no_embeddings": True,
            "local_first": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "vector-index dry-run proof json")
        (out_dir / _PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "vector-index dry-run proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof


# --- Prompt 19: apply build proof ----------------------------------------------------------------


def _mock_vector_writer(
    nodes: list[dict[str, Any]], *, persist_dir: str, config: dict[str, Any]
) -> dict[str, Any]:
    """Deterministic offline writer for proofs/tests: real LlamaIndex pipeline + `MockEmbedding`.

    Requires only `llama-index-core` (`[retrieval]`); bypasses the HF local embedding import entirely by
    passing embed_model. Used by build-apply-proof so it passes on base + retrieval install (no local).
    """
    from llama_index.core.embeddings import MockEmbedding

    dim = int(load_embedding_vector_policy_seed().get("embedding_dim", 384))
    return _llamaindex_vector_writer(
        nodes, persist_dir=persist_dir, config=config, embed_model=MockEmbedding(embed_dim=dim)
    )


def _empty_migrated_db(tmp: str) -> str:
    """A schema-current but empty DB (no approved sources) — exercises the blocked apply path."""
    from hb_assistant.store.migrator import SQLiteMigrator

    db = str(Path(tmp) / "empty.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return db


def _guard_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """Return the table's guard CHECK(=0) columns (the `*_persisted` / `*_performed` / bypass flags)."""
    cols = [str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return [
        c
        for c in cols
        if c.endswith(("_persisted", "_performed")) or c.endswith("_bypassed_policy")
    ]


def _render_apply_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Vector Index Build (Apply) Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- applied_run_id: {proof['applied_run_id']}",
        f"- applied_item_count: {proof['applied_item_count']}",
        f"- embedding_dim: {proof['embedding_dim']}",
        f"- vectors_written_outside_sqlite: {proof['vectors_written_outside_sqlite']}",
        f"- vectors_persisted_to_sqlite: {proof['vectors_persisted_to_sqlite']} (must be false)",
        f"- run_record_guard_clean: {proof['run_record_guard_clean']}",
        f"- item_records_guard_clean: {proof['item_records_guard_clean']}",
        f"- no_forbidden_persisted_columns: {proof['no_forbidden_persisted_columns']}",
        f"- blocked_no_indexable_nodes: {proof['blocked_no_indexable_nodes']}",
        f"- blocked_sdk_absent: {proof['blocked_sdk_absent']}",
        "",
        "## Build-rule cases",
        "",
    ]
    for c in proof["cases"]:
        lines.append(
            f"- [{'ok' if c['passed'] else 'FAIL'}] {c['name']}: "
            f"expected_indexable={c['expected_indexable']} indexable={c['indexable']} "
            f"violations={len(c['violations'])}"
        )
    lines.append("")
    return "\n".join(lines)


def build_vector_index_apply_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: a guard-clean apply embeds approved nodes, writes vectors **outside SQLite**,
    persists metadata-only receipts, and blocks when there are no indexable nodes or the SDK is absent.

    Uses `_mock_vector_writer` (injects MockEmbedding) so the proof runs with only the `retrieval` extra
    (core); it never exercises the real HF import path. The real `build --apply` (default writer) requires
    `retrieval-local` for local embeddings and will block with `local_embedding_not_ready` otherwise.
    """
    apply_contract = load_vector_index_apply_contract()
    forbidden_cols = {str(c) for c in apply_contract.get("forbidden_persisted_fields", [])}

    with tempfile.TemporaryDirectory() as tmp:
        db = _proof_db(tmp)
        persist_root = str(Path(tmp) / "vector_store")
        applied = build_vector_index_apply(
            db, writer=_mock_vector_writer, persist_root=persist_root
        )

        run_id = applied.get("run_id", "")
        persist_dir = Path(persist_root) / str(run_id)
        vectors_outside_sqlite = persist_dir.exists() and any(persist_dir.iterdir())

        conn = sqlite3.connect(db)
        try:
            run_row = conn.execute(
                f"SELECT status, item_count FROM {_RUNS_TABLE} WHERE run_id = ?", (run_id,)
            ).fetchone()
            run_guard_cols = _guard_columns(conn, _RUNS_TABLE)
            run_guard_sum = conn.execute(
                f"SELECT {'+'.join(run_guard_cols)} FROM {_RUNS_TABLE} WHERE run_id = ?", (run_id,)
            ).fetchone()
            item_rows = conn.execute(
                f"SELECT COUNT(*) FROM {_ITEMS_TABLE} WHERE run_id = ?", (run_id,)
            ).fetchone()
            item_guard_cols = _guard_columns(conn, _ITEMS_TABLE)
            item_guard_sum = conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(item_guard_cols)}), 0) FROM {_ITEMS_TABLE} "
                "WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            run_cols = {str(r[1]) for r in conn.execute(f"PRAGMA table_info({_RUNS_TABLE})")}
            item_cols = {str(r[1]) for r in conn.execute(f"PRAGMA table_info({_ITEMS_TABLE})")}
        finally:
            conn.close()

        # Blocked path: a schema-current but empty DB has no indexable nodes.
        empty_db = _empty_migrated_db(tmp)
        blocked = build_vector_index_apply(empty_db, writer=_mock_vector_writer, persist_root=tmp)

    applied_ok = applied.get("status") == "applied" and int(applied.get("total_items", 0)) >= 1
    run_persisted = run_row is not None and run_row[0] == "applied"
    run_guard_clean = bool(run_guard_sum) and int(run_guard_sum[0] or 0) == 0
    items_match = (
        run_persisted
        and item_rows is not None
        and int(item_rows[0]) == int(applied.get("total_items", -1))
    )
    item_guard_clean = bool(item_guard_sum) and int(item_guard_sum[0] or 0) == 0
    no_forbidden_columns = not (forbidden_cols & (run_cols | item_cols))
    blocked_no_nodes = (
        blocked.get("status") == "apply_blocked"
        and blocked.get("blocker_reason") == "no_indexable_nodes"
    )

    cases = _rule_cases()
    proof_passed = (
        applied_ok
        and applied.get("vectors_persisted_to_sqlite") is False
        and vectors_outside_sqlite
        and run_persisted
        and run_guard_clean
        and items_match
        and item_guard_clean
        and no_forbidden_columns
        and blocked_no_nodes
        and all(c["passed"] for c in cases)
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_vector_index_apply",
        "command": "second-brain retrieval llamaindex build-apply-proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "applied_run_id": run_id,
        "applied_item_count": int(applied.get("total_items", 0)),
        "embedding_dim": int(applied.get("embedding_dim", 0)),
        "vectors_written_outside_sqlite": vectors_outside_sqlite,
        "vectors_persisted_to_sqlite": applied.get("vectors_persisted_to_sqlite"),
        "run_record_guard_clean": run_guard_clean,
        "item_records_guard_clean": item_guard_clean,
        "no_forbidden_persisted_columns": no_forbidden_columns,
        "blocked_no_indexable_nodes": blocked_no_nodes,
        # SDK-absent fail-closed is enforced by the same gate and verified in the unit suite
        # (monkeypatched); the SDK is installed here, so this proof exercises the applied + blocked paths.
        "blocked_sdk_absent": "unit_tested",
        "case_count": len(cases),
        "cases": cases,
        "metadata_only": True,
        "guardrails": {
            "read_only": False,
            "no_raw": True,
            "no_writeback": True,
            "approved_manifest_only_input": True,
            "vectors_outside_sqlite": True,
            "no_raw_vector_content_in_sqlite": True,
            "local_first": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "vector-index apply proof json")
        (out_dir / _APPLY_PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_apply_proof_md(proof)
        _assert_no_raw(markdown, "vector-index apply proof markdown")
        (out_dir / _APPLY_PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _APPLY_PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _APPLY_PROOF_MD)

    return proof
