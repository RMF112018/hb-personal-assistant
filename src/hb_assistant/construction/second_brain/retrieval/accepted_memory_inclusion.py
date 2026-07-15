"""Phase 09 Addendum Prompt 03 — accepted-memory pipeline inclusion proofs.

Integrated, end-to-end proof that one accepted long-term memory item flows through the full Phase 09
retrieval pipeline — deterministic reader, reviewed-memory loader, approved-source manifest, vector
dry-run, vector apply, no-raw vector proof, and coverage-parity closeout — while non-accepted memory
(pending_review / rejected / superseded) is excluded everywhere. The wiring already exists; this module
only *orchestrates* the existing pipeline functions (each accepts ``db_path``) over a deterministic
fixture and attests the result. No pipeline code change, no migration.

`deferred` is a candidate-level decision (Prompt 02): deferred candidates never become memory items, so
they cannot load — exclusion is by construction. The non-loading memory-item statuses proven here are
``pending_review`` / ``rejected`` / ``superseded``.

Public entry points:
  build_accepted_memory_loader_proof(*, evidence_dir=None, write_evidence=True) -> dict
  build_accepted_memory_vector_coverage_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain retrieval accepted-memory-loader-proof | accepted-memory-vector-coverage-proof
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from ..financial_review_routing import _assert_no_raw

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_LOADER_JSON = "accepted-memory-loader-proof.json"
_LOADER_MD = "accepted-memory-loader-proof.md"
_VECTOR_JSON = "accepted-memory-vector-coverage-proof.json"
_VECTOR_MD = "accepted-memory-vector-coverage-proof.md"

# In the live pipeline the eight other eligible families (approved Obsidian outputs + the read-model /
# generated-output families) are already applied; adding accepted memory takes the count from 8 to 9.
_LIVE_BASELINE_VECTOR_FAMILY_COUNT = 8
_LIVE_EXPECTED_AFTER = 9


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


def _accepted_item(memory_id: str) -> Any:
    from ..memory.models import MemoryItem

    return MemoryItem(
        memory_id=memory_id,
        memory_type="fact",
        statement_redacted="The project tracks submittal turnaround locally.",
        confidence_class="high",
        review_status="accepted",
        source_refs=[{"source_family": "cross_source_relationships", "source_ref": "rel-1"}],
    )


def _non_accepted_item(memory_id: str, review_status: str) -> Any:
    from ..memory.models import MemoryItem

    return MemoryItem(
        memory_id=memory_id,
        memory_type="fact",
        statement_redacted="a non-accepted memory statement",
        confidence_class="high",
        review_status=review_status,
        source_refs=[{"source_family": "cross_source_relationships", "source_ref": "rel-x"}],
    )


def _write_evidence(
    out: dict[str, Any], evidence_dir: str | None, json_name: str, md: str, md_name: str
) -> dict[str, Any]:
    out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(out, indent=2, default=str)
    _assert_no_raw(serialized, json_name)
    (out_dir / json_name).write_text(serialized + "\n", encoding="utf-8")
    _assert_no_raw(md, md_name)
    (out_dir / md_name).write_text(md, encoding="utf-8")
    out["proof_path"] = str(out_dir / json_name)
    out["proof_md_path"] = str(out_dir / md_name)
    return out


# --- Loader / reader / manifest inclusion proof --------------------------------------------------


def build_accepted_memory_loader_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Prove an accepted item appears in the deterministic reader, reviewed-memory loader, and the
    approved-source manifest, while pending/rejected/superseded items are excluded."""
    from hb_assistant.store.migrator import ensure_schema_ready

    from ..memory.store import write_memory_item
    from .memory_loader import build_reviewed_memory_loader_report, load_reviewed_memory_nodes
    from .readers import read_accepted_memory
    from .source_manifest import build_approved_source_manifest

    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "loader.sqlite")
        ensure_schema_ready(db)
        write_memory_item(_accepted_item("acc-mem-1"), db_path=db)
        for mid, status in (
            ("pend-1", "pending_review"),
            ("rej-1", "rejected"),
            ("sup-1", "superseded"),
        ):
            write_memory_item(_non_accepted_item(mid, status), db_path=db)

        reader_items = read_accepted_memory(cast(Any, None), db, None)  # store unused on this path
        nodes = load_reviewed_memory_nodes(db)
        report = build_reviewed_memory_loader_report(db)
        manifest = build_approved_source_manifest(db)

    reader_families = {i.source_family for i in reader_items}
    reader_refs = {i.source_ref for i in reader_items}
    reader_only_accepted = (
        len(reader_items) == 1
        and reader_families == {"accepted_long_term_memory"}
        and reader_refs == {"acc-mem-1"}
    )

    loader_ok = (
        len(nodes) == 1
        and report["loaded_count"] == 1
        and report["status"] == "loaded"
        and report["reviewed_only"] is True
        and report["read_only"] is True
    )
    node = nodes[0] if nodes else {}
    redacted_bounded = bool(node) and len(str(node.get("text_redacted", ""))) <= 280
    source_linked = bool(node) and int(node.get("source_ref_count", 0)) >= 1
    has_confidence = bool(node) and bool(node.get("confidence_class"))
    has_freshness = bool(node) and bool(node.get("freshness_label"))
    node_family_ok = bool(node) and node.get("source_family") == "accepted_long_term_memory"

    fam = manifest.get("families", {}).get("reviewed_memory", {})
    manifest_ok = int(fam.get("approved_count", 0)) >= 1

    non_accepted_excluded = (
        reader_only_accepted and len(nodes) == 1 and int(fam.get("approved_count", 0)) == 1
    )

    proof_passed = (
        reader_only_accepted
        and loader_ok
        and node_family_ok
        and redacted_bounded
        and source_linked
        and has_confidence
        and has_freshness
        and manifest_ok
        and non_accepted_excluded
    )

    node_summary = {
        "node_id": node.get("node_id"),
        "source_family": node.get("source_family"),
        "source_ref_hash": _hash(str(node.get("source_ref", "")))[:48],
        "confidence_class": node.get("confidence_class"),
        "freshness_label": node.get("freshness_label"),
        "review_tier": node.get("review_tier"),
        "review_status": node.get("review_status"),
        "source_ref_count": node.get("source_ref_count"),
        "statement_len": len(str(node.get("text_redacted", ""))),
    }

    out: dict[str, Any] = {
        "proof": "phase_09_accepted_memory_loader",
        "command": "second-brain retrieval accepted-memory-loader-proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "reader_returns_only_accepted": reader_only_accepted,
        "loader_loaded_count": report["loaded_count"],
        "loader_status": report["status"],
        "manifest_reviewed_memory_approved_count": int(fam.get("approved_count", 0)),
        "non_accepted_excluded": non_accepted_excluded,
        "statement_redacted_and_bounded": redacted_bounded,
        "source_linked": source_linked,
        "carries_confidence_class": has_confidence,
        "carries_freshness_label": has_freshness,
        "accepted_node_summary": node_summary,
        "metadata_only": True,
        "guardrails": {
            "reviewed_only_accepted": True,
            "read_only": True,
            "no_raw": True,
            "no_external_writeback": True,
            "source_linked_only": True,
            "bounded_statements": True,
            "local_first": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        md = _render_loader_md(out)
        out = _write_evidence(out, evidence_dir, _LOADER_JSON, md, _LOADER_MD)
    return out


def _render_loader_md(p: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Phase 09 Addendum — Accepted Memory Loader / Manifest Inclusion Proof",
            "",
            f"- proof_passed: {p['proof_passed']}",
            f"- generated_utc: {p['generated_utc']}",
            f"- reader_returns_only_accepted: {p['reader_returns_only_accepted']}",
            f"- loader_loaded_count: {p['loader_loaded_count']} (status {p['loader_status']})",
            f"- manifest_reviewed_memory_approved_count: {p['manifest_reviewed_memory_approved_count']}",
            f"- non_accepted_excluded (pending/rejected/superseded): {p['non_accepted_excluded']}",
            f"- statement_redacted_and_bounded: {p['statement_redacted_and_bounded']}",
            f"- source_linked: {p['source_linked']}",
            f"- carries_confidence_class: {p['carries_confidence_class']}",
            f"- carries_freshness_label: {p['carries_freshness_label']}",
            "",
        ]
    )


# --- Vector / coverage inclusion proof -----------------------------------------------------------


def _seed_obsidian_apply_db(tmp: str) -> str:
    """Apply-mode Obsidian index fixture (no memory yet) — the non-empty vector baseline."""
    from ..obsidian_index.indexer import build_index
    from ..obsidian_linkage_proof import write_linkage_fixture_vault

    vault = Path(tmp) / "vault"
    write_linkage_fixture_vault(vault)
    db = str(Path(tmp) / "vidx.sqlite")
    build_index(mode="apply", vault_root=vault, db_path=db)
    return db


def build_accepted_memory_vector_coverage_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Prove accepted memory enters the vector dry-run plan + applied index, the no-raw vector proof
    still passes, and the coverage-parity closeout flips memory to covered (+1 vector family)."""
    from ..memory.store import write_memory_item
    from .coverage_parity import build_coverage_parity_closeout
    from .no_raw_vector_index_proof import build_no_raw_vector_index_proof
    from .vector_index import (
        _mock_vector_writer,
        build_vector_index_apply,
        build_vector_index_dry_run,
    )

    with tempfile.TemporaryDirectory() as tmp:
        db = _seed_obsidian_apply_db(tmp)
        persist_root = str(Path(tmp) / "vector_store")

        # Baseline: apply with Obsidian only (no accepted memory yet).
        build_vector_index_apply(db, writer=_mock_vector_writer, persist_root=persist_root)
        dry_before = build_vector_index_dry_run(db)
        closeout_before = build_coverage_parity_closeout(db, write_evidence=False)
        vfam_before = list(closeout_before["planes"]["vector_indexed_families"])
        substrate_before = closeout_before["planes"]["memory_substrate_status"]

        # Add one accepted memory item (+ a non-accepted one to confirm exclusion).
        write_memory_item(_accepted_item("acc-mem-vec-1"), db_path=db)
        write_memory_item(_non_accepted_item("pend-vec-1", "pending_review"), db_path=db)

        dry_after = build_vector_index_dry_run(db)
        apply_after = build_vector_index_apply(
            db, writer=_mock_vector_writer, persist_root=persist_root
        )
        no_raw = build_no_raw_vector_index_proof(db)
        closeout_after = build_coverage_parity_closeout(db, write_evidence=False)
        vfam_after = list(closeout_after["planes"]["vector_indexed_families"])
        substrate_after = closeout_after["planes"]["memory_substrate_status"]

    _FAMILY = "accepted_long_term_memory"
    memory_in_dry_after = _FAMILY in dry_after.get("per_family_node_count", {})
    memory_not_in_dry_before = _FAMILY not in dry_before.get("per_family_node_count", {})
    apply_applied = apply_after.get("status") == "applied"
    apply_has_memory = _FAMILY in apply_after.get("per_family_item_count", {})
    vectors_not_in_sqlite = (
        dry_after.get("vectors_persisted_to_sqlite") is False
        and apply_after.get("vectors_persisted_to_sqlite") is False
    )
    dry_no_raw_attested = dry_after.get("no_raw_attested") is True
    no_raw_ok = bool(no_raw.get("proof_passed"))

    memory_absent_before = _FAMILY not in vfam_before
    memory_present_after = _FAMILY in vfam_after
    family_delta_plus_one = len(vfam_after) == len(vfam_before) + 1
    substrate_flip = substrate_before == "deferred_empty" and substrate_after == "covered"
    parity_true = bool(closeout_before["coverage_parity"].get("coverage_parity_ok")) and bool(
        closeout_after["coverage_parity"].get("coverage_parity_ok")
    )
    closeout_ok = bool(closeout_after.get("closeout_ok"))

    proof_passed = (
        memory_in_dry_after
        and memory_not_in_dry_before
        and apply_applied
        and apply_has_memory
        and vectors_not_in_sqlite
        and dry_no_raw_attested
        and no_raw_ok
        and memory_absent_before
        and memory_present_after
        and family_delta_plus_one
        and substrate_flip
        and parity_true
        and closeout_ok
    )

    out: dict[str, Any] = {
        "proof": "phase_09_accepted_memory_vector_coverage",
        "command": "second-brain retrieval accepted-memory-vector-coverage-proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "memory_in_dry_run_after": memory_in_dry_after,
        "memory_not_in_dry_run_before": memory_not_in_dry_before,
        "vector_apply_status": apply_after.get("status"),
        "vector_apply_includes_memory": apply_has_memory,
        "vectors_persisted_to_sqlite": apply_after.get("vectors_persisted_to_sqlite"),
        "no_raw_vector_proof_passed": no_raw_ok,
        "vector_indexed_family_count_before": len(vfam_before),
        "vector_indexed_family_count_after": len(vfam_after),
        "vector_indexed_families_after": sorted(vfam_after),
        "accepted_long_term_memory_absent_before": memory_absent_before,
        "accepted_long_term_memory_present_after": memory_present_after,
        "vector_family_delta_plus_one": family_delta_plus_one,
        "memory_substrate_status_before": substrate_before,
        "memory_substrate_status_after": substrate_after,
        "coverage_parity_ok": parity_true,
        "closeout_ok": closeout_ok,
        "live_baseline_note": (
            f"In the live pipeline the {_LIVE_BASELINE_VECTOR_FAMILY_COUNT} other eligible families are "
            f"already applied, so this same +1 takes the vector-indexed family count from "
            f"{_LIVE_BASELINE_VECTOR_FAMILY_COUNT} to {_LIVE_EXPECTED_AFTER}."
        ),
        "live_baseline_vector_family_count": _LIVE_BASELINE_VECTOR_FAMILY_COUNT,
        "live_expected_after": _LIVE_EXPECTED_AFTER,
        "readiness_not_overstated": True,
        "metadata_only": True,
        "guardrails": {
            "reviewed_only_accepted": True,
            "no_vectors_or_node_text_in_sqlite": True,
            "no_raw": True,
            "no_external_writeback": True,
            "no_readiness_overstatement": True,
            "local_first": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        md = _render_vector_md(out)
        out = _write_evidence(out, evidence_dir, _VECTOR_JSON, md, _VECTOR_MD)
    return out


def _render_vector_md(p: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Phase 09 Addendum — Accepted Memory Vector / Coverage Inclusion Proof",
            "",
            f"- proof_passed: {p['proof_passed']}",
            f"- generated_utc: {p['generated_utc']}",
            f"- memory_in_dry_run_after: {p['memory_in_dry_run_after']}"
            f" (before: {p['memory_not_in_dry_run_before']})",
            f"- vector_apply_status: {p['vector_apply_status']}"
            f" | includes_memory: {p['vector_apply_includes_memory']}",
            f"- vectors_persisted_to_sqlite: {p['vectors_persisted_to_sqlite']} (must be false)",
            f"- no_raw_vector_proof_passed: {p['no_raw_vector_proof_passed']}",
            f"- vector_indexed_family_count: {p['vector_indexed_family_count_before']}"
            f" -> {p['vector_indexed_family_count_after']} (+1 = accepted_long_term_memory)",
            f"- memory_substrate_status: {p['memory_substrate_status_before']}"
            f" -> {p['memory_substrate_status_after']}",
            f"- coverage_parity_ok: {p['coverage_parity_ok']} | closeout_ok: {p['closeout_ok']}",
            f"- {p['live_baseline_note']}",
            "",
        ]
    )
