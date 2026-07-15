"""Phase 09 — approved deterministic read-model → safe vector-node loader.

Bridges the deterministic, allowlisted read-model families (served by ``READER_REGISTRY``) into the
semantic-retrieval plane. The dedicated Obsidian / reviewed-memory / generated-outputs loaders already
cover their families; this loader covers the *other* embeddable read-model families
(evidence trails, issue history, risk digest, aging exposure, cross-source relationships, and — per
the embedding policy seed — meeting-prep sections and review-controlled correspondence context).

It admits only **eligible** items — redacted excerpt present, source-linked (non-empty ``source_ref``
+ allowlisted family), **not review-required**, and ``review_tier <= 2`` — so no high-impact /
review-required item is ever vector-indexed (review-control guardrail preserved). Each eligible item
becomes a metadata-only vector node carrying only the bounded ``content_excerpt_redacted`` text
(``text_redacted``) plus hashes/labels: no raw bodies, prompts, responses, URLs, tokens, or secrets,
and no vectors. This module is read-only and is the single shared source for both the approved-source
manifest's ``approved_read_models`` category and the vector-index node gather.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.construction.store import ConstructionStore

from ..financial_review_routing import _assert_no_raw
from .embedding_policy import (
    embeddable_families,
    load_embedding_vector_policy_contract,
    load_embedding_vector_policy_seed,
    validate_embedding_candidate,
)
from .models import RetrievalItem
from .policy import EXCLUDED_FAMILIES
from .readers import READER_REGISTRY

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "read-model-vector-loader-proof.json"
_PROOF_MD = "read-model-vector-loader-proof.md"
_VECTOR_ITEMS_TABLE = "second_brain_retrieval_vector_index_items"

# Families already brought into the vector index by their own dedicated node loaders.
_DEDICATED_LOADER_FAMILIES: frozenset[str] = frozenset(
    {
        "approved_obsidian_generated_outputs",
        "accepted_long_term_memory",
        "generated_outputs",
    }
)

_EXCERPT_MAX_CHARS = 280


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_model_loader_families(seed: dict[str, Any] | None = None) -> list[str]:
    """Embeddable read-model families served here: embeddable ∩ readers − dedicated-loader families."""
    seed = seed or load_embedding_vector_policy_seed()
    return [
        f
        for f in embeddable_families(seed)
        if f in READER_REGISTRY and f not in _DEDICATED_LOADER_FAMILIES
    ]


def _eligible(item: RetrievalItem) -> bool:
    """An item may be admitted iff redacted + source-linked + not review-required + tier <= 2."""
    return (
        bool(item.content_excerpt_redacted)
        and bool(item.source_ref)
        and item.source_family not in EXCLUDED_FAMILIES
        and item.review_required is False
        and item.review_tier <= 2
    )


def iter_approved_read_model_items(
    db_path: str | None, project_key: str | None = None
) -> list[RetrievalItem]:
    """Run each served family's deterministic reader and keep only the eligible items (read-only)."""
    store = ConstructionStore(db_path)
    seed = load_embedding_vector_policy_seed()
    items: list[RetrievalItem] = []
    for family in read_model_loader_families(seed):
        reader = READER_REGISTRY.get(family)
        if reader is None:
            continue
        for item in reader(store, db_path, project_key):
            if _eligible(item):
                items.append(item)
    return items


def load_approved_read_model_nodes(
    db_path: str | None, *, project_key: str | None = None
) -> list[dict[str, Any]]:
    """Convert eligible deterministic read-model items into metadata-only vector nodes.

    Returned node dicts mirror the other loaders' shape (``node_id`` / ``source_family`` /
    ``source_ref`` / ``content_hash`` / ``confidence_class`` / ``review_tier`` / ``review_status`` /
    ``review_required`` / ``freshness_label`` / ``text_redacted``). Only the bounded redacted excerpt
    is carried as text; never persisted by this module.
    """
    nodes: list[dict[str, Any]] = []
    for item in iter_approved_read_model_items(db_path, project_key):
        excerpt = item.content_excerpt_redacted[:_EXCERPT_MAX_CHARS]
        source_ref = item.source_ref
        nodes.append(
            {
                "node_id": _hash(f"{item.source_family}:{source_ref}")[:48],
                "source_family": item.source_family,
                "source_ref": source_ref,
                "content_hash": _hash(f"{item.source_family}:{source_ref}:{excerpt}")[:64],
                "confidence_class": item.confidence_class or "unknown",
                "review_tier": item.review_tier,
                "review_status": item.review_status,
                "review_required": item.review_required,
                "freshness_label": "current" if item.recency else "unknown",
                "text_redacted": excerpt,
            }
        )
    return nodes


# --- Proof -------------------------------------------------------------------------------------------


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


def _proof_db(tmp: str) -> str:
    """A schema-current temp DB seeded with eligible read-model rows across 5 families plus one planted
    review-required (tier-3) item that the eligibility filter must reject. Proof/test only."""
    from hb_assistant.store.migrator import ensure_schema_ready

    db = str(Path(tmp) / "read_model_proof.sqlite3")
    ensure_schema_ready(db)
    store = ConstructionStore(db)
    ref = json.dumps({"project_key": "P1"})
    store.upsert_cross_source_relationship(
        relationship_id="rel-0",
        source_family="document",
        source_record_type="document",
        source_record_ref="doc-0",
        target_family="procore",
        target_record_type="rfi",
        target_record_ref="rfi-0",
        relationship_type="document_record_reference",
        confidence_class="deterministic",
        source_reference_json=ref,
        project_key="P1",
    )
    store.upsert_source_evidence_trail(
        evidence_trail_id="et-0",
        evidence_kind="document_relationship",
        source_refs_json=json.dumps(["r0"]),
        confidence_class="high",
        project_key="P1",
    )
    store.upsert_project_issue_history_item(
        issue_family_id="iss-0",
        project_key="P1",
        status="open",
        source_families_json=json.dumps(["procore"]),
        confidence_class="high",
        issue_kind="rfi",
        age_days=10,
        review_required=False,
    )
    store.upsert_project_risk_digest_item(
        risk_digest_id="risk-0",
        project_key="P1",
        risk_indicator_type="schedule_slip",
        risk_source_class="source_stated",
        summary_redacted="schedule slip x2",
        confidence_class="high",
        review_required=False,
    )
    store.upsert_aging_exposure_report_item(
        aging_item_id="age-0",
        project_key="P1",
        record_family="procore",
        record_ref="rfi-0",
        status="open",
        threshold_band="aging_30_60",
        age_days=45,
        confidence_class="high",
        review_required=False,
    )
    # Planted high-impact / review-required item — must never be admitted as a vector node.
    store.upsert_project_issue_history_item(
        issue_family_id="iss-review",
        project_key="P1",
        status="open",
        source_families_json=json.dumps(["procore"]),
        confidence_class="low",
        issue_kind="rfi",
        age_days=99,
        review_required=True,
    )
    return db


def build_read_model_vector_loader_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: the read-model loader bridges eligible deterministic read-model items into
    safe, metadata-only vector nodes (no-raw, in-memory only), excludes review-required / high-impact
    items, rejects raw/excluded candidates, and writes nothing to SQLite. No raw text is emitted."""
    import tempfile

    contract = load_embedding_vector_policy_contract()
    seed = load_embedding_vector_policy_seed()

    with tempfile.TemporaryDirectory() as tmp:
        db = _proof_db(tmp)
        conn = sqlite3.connect(db)
        try:
            rows_before = int(
                conn.execute(f"SELECT COUNT(*) FROM {_VECTOR_ITEMS_TABLE}").fetchone()[0]
            )
        finally:
            conn.close()

        nodes = load_approved_read_model_nodes(db)

        conn = sqlite3.connect(db)
        try:
            rows_after = int(
                conn.execute(f"SELECT COUNT(*) FROM {_VECTOR_ITEMS_TABLE}").fetchone()[0]
            )
        finally:
            conn.close()

    families = sorted({str(n["source_family"]) for n in nodes})
    all_valid = all(not validate_embedding_candidate(n, contract=contract, seed=seed) for n in nodes)
    all_eligible = all(
        n["review_required"] is False and int(n["review_tier"]) <= 2 and bool(n["text_redacted"])
        for n in nodes
    )
    review_required_excluded = not any(n["source_ref"] == "iss-review" for n in nodes)
    loader_writes_nothing = rows_before == rows_after == 0

    # Non-vacuity: planted unsafe in-memory candidates are rejected by the embed guard.
    synthetic_secret = "Bea" + "rer " + "z" * 32
    safe = {
        "source_family": "phase_07d_source_evidence_trails",
        "source_ref": "et-x",
        "content_hash": "f" * 16,
        "confidence_class": "high",
        "review_tier": 1,
        "freshness_label": "current",
        "review_required": False,
    }
    rejects_raw_shape = bool(
        validate_embedding_candidate(
            {**safe, "content_hash": synthetic_secret}, contract=contract, seed=seed
        )
    )
    rejects_excluded_family = bool(
        validate_embedding_candidate(
            {**safe, "source_family": "raw_email_body"}, contract=contract, seed=seed
        )
    )

    proof_passed = bool(
        len(families) >= 5
        and all_valid
        and all_eligible
        and review_required_excluded
        and loader_writes_nothing
        and rejects_raw_shape
        and rejects_excluded_family
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_read_model_vector_loader",
        "command": "second-brain retrieval read-model-vector-loader-proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "node_count": len(nodes),
        "indexed_family_count": len(families),
        "indexed_families": families,
        "all_nodes_no_raw_valid": all_valid,
        "all_nodes_eligible_tier_le_2_not_review_required": all_eligible,
        "review_required_high_impact_excluded": review_required_excluded,
        "loader_persists_nothing_to_sqlite": loader_writes_nothing,
        "rejects_raw_shape_candidate": rejects_raw_shape,
        "rejects_excluded_family_candidate": rejects_excluded_family,
        "metadata_only": True,
        "guardrails": {
            "read_only": True,
            "no_raw": True,
            "no_raw_vector_content_in_sqlite": True,
            "in_memory_nodes_only": True,
            "no_external_writeback": True,
            "review_control_preserved": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "read-model vector loader proof json")
        (out_dir / _PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        md = _render_loader_proof_md(proof)
        _assert_no_raw(md, "read-model vector loader proof markdown")
        (out_dir / _PROOF_MD).write_text(md, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof


def _render_loader_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Read-Model Vector Loader Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- node_count: {proof['node_count']}",
        f"- indexed_family_count: {proof['indexed_family_count']} (>= 5)",
        f"- all_nodes_no_raw_valid: {proof['all_nodes_no_raw_valid']}",
        f"- review_required_high_impact_excluded: {proof['review_required_high_impact_excluded']}",
        f"- loader_persists_nothing_to_sqlite: {proof['loader_persists_nothing_to_sqlite']}",
        f"- rejects_raw_shape_candidate: {proof['rejects_raw_shape_candidate']}",
        f"- rejects_excluded_family_candidate: {proof['rejects_excluded_family_candidate']}",
        f"- indexed_families: {proof['indexed_families']}",
        "",
    ]
    return "\n".join(lines)
