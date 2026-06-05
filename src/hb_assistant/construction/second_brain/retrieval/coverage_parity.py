"""Phase 09 — reader / manifest / vector coverage-parity proofs (read-only, advisory).

Two fail-closed, metadata-only proof surfaces over the retrieval coverage planes:

- ``build_reader_registry_parity_proof`` — proves the deterministic retrieval allowlist
  (``ALLOWLISTED_SOURCE_FAMILIES``) and the reader registry (``READER_REGISTRY``) are in parity: every
  allowlisted family has a registered reader (or an explicitly documented intentional deferral with a
  blocking reason). DB-independent (static registry/policy).
- ``build_coverage_parity_closeout`` — aggregates the coverage-parity report (deterministic / approved
  manifest / vector-indexed / memory / deferred planes) with the three approved-read-model proofs
  (reader-registry parity, approved-read-model manifest, read-model vector loader) into one closeout.

Both emit JSON+MD evidence (guard-clean; ``_assert_no_raw`` over the serialized output). No raw content,
prompts, responses, tokens, URLs, or secrets — only family names, counts, and boolean flags. Read-only;
never writes to SQLite; makes no determination; does not overstate readiness (empty manifest / vector /
memory families are reported deferred, never as a parity failure).
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..corpus_balance_mart import build_coverage_parity_report
from ..financial_review_routing import _assert_no_raw
from .policy import ALLOWLISTED_SOURCE_FAMILIES
from .readers import READER_REGISTRY

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PARITY_JSON = "reader-registry-parity-proof.json"
_PARITY_MD = "reader-registry-parity-proof.md"
_CLOSEOUT_JSON = "coverage-parity-closeout.json"
_CLOSEOUT_MD = "coverage-parity-closeout.md"

# Allowlisted families intentionally deferred (no reader) with a documented blocking reason. Empty
# now — every allowlisted family is reader-backed. Kept as the explicit, auditable deferral surface.
_DEFERRED_READER_FAMILIES: dict[str, str] = {}


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


def build_reader_registry_parity_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Prove deterministic-allowlist <-> reader-registry parity (static; fail-closed).

    ``proof_passed`` iff every allowlisted family has a reader or an explicitly documented deferral.
    """
    allowlisted = list(ALLOWLISTED_SOURCE_FAMILIES)
    reader_backed = sorted(f for f in allowlisted if f in READER_REGISTRY)
    missing = sorted(
        f for f in allowlisted if f not in READER_REGISTRY and f not in _DEFERRED_READER_FAMILIES
    )
    deferred = {f: _DEFERRED_READER_FAMILIES[f] for f in allowlisted if f in _DEFERRED_READER_FAMILIES}
    # Readers registered for a non-allowlisted family would be a policy drift — surface it.
    extra = sorted(f for f in READER_REGISTRY if f not in allowlisted)

    proof_passed = not missing and not extra

    proof: dict[str, Any] = {
        "proof": "phase_09_reader_registry_parity",
        "command": "second-brain retrieval reader-registry-parity-proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "deterministic_allowlisted_family_count": len(allowlisted),
        "deterministic_reader_family_count": len(reader_backed),
        "allowlisted_families": sorted(allowlisted),
        "reader_backed_families": reader_backed,
        "missing_reader_families": missing,
        "deferred_reader_families": deferred,
        "non_allowlisted_reader_families": extra,
        "parity_ok": proof_passed,
        "metadata_only": True,
        "guardrails": {
            "read_only": True,
            "no_raw": True,
            "no_external_writeback": True,
            "advisory_only": True,
            "no_determination": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "reader-registry-parity proof json")
        (out_dir / _PARITY_JSON).write_text(serialized + "\n", encoding="utf-8")
        md = _render_parity_md(proof)
        _assert_no_raw(md, "reader-registry-parity proof markdown")
        (out_dir / _PARITY_MD).write_text(md, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PARITY_JSON)
        proof["proof_md_path"] = str(out_dir / _PARITY_MD)

    return proof


def _render_parity_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Reader Registry Parity Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- deterministic_allowlisted_family_count: {proof['deterministic_allowlisted_family_count']}",
        f"- deterministic_reader_family_count: {proof['deterministic_reader_family_count']}",
        f"- missing_reader_families: {proof['missing_reader_families']} (must be empty)",
        f"- deferred_reader_families: {sorted(proof['deferred_reader_families'])}",
        f"- non_allowlisted_reader_families: {proof['non_allowlisted_reader_families']} (must be empty)",
        "",
        "## Reader-backed families",
        "",
    ]
    lines += [f"- {f}" for f in proof["reader_backed_families"]]
    lines.append("")
    return "\n".join(lines)


def build_coverage_parity_closeout(
    db_path: str | None = None, *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Aggregate the coverage-parity report + the three approved-read-model proofs into a closeout.

    The report is computed over ``db_path`` (default: operator DB) and reflects real coverage; the three
    sub-proofs run over their own controlled temporary DBs. ``closeout_ok`` requires reader-registry
    parity and all three sub-proofs to pass. Empty manifest / vector / memory families are reported
    deferred (not a failure) — no readiness overstatement.
    """
    from .read_model_loader import build_read_model_vector_loader_proof
    from .source_manifest import build_approved_read_model_manifest_proof

    report = build_coverage_parity_report(db_path)
    parity = build_reader_registry_parity_proof(write_evidence=False)
    manifest_proof = build_approved_read_model_manifest_proof(write_evidence=False)
    loader_proof = build_read_model_vector_loader_proof(write_evidence=False)

    sub = {
        "reader_registry_parity": bool(parity["proof_passed"]),
        "approved_read_model_manifest": bool(manifest_proof["proof_passed"]),
        "read_model_vector_loader": bool(loader_proof["proof_passed"]),
    }
    closeout_ok = bool(report.get("coverage_parity_ok")) and all(sub.values())

    closeout: dict[str, Any] = {
        "proof": "phase_09_coverage_parity_closeout",
        "command": "second-brain retrieval coverage-parity-closeout",
        "phase": "09",
        "closeout_ok": closeout_ok,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "coverage_parity": report,
        "sub_proofs_passed": sub,
        "planes": {
            "deterministic_reader_families": report.get("deterministic_reader_families", []),
            "approved_manifest_families": report.get("approved_manifest_families", []),
            "vector_indexed_families": report.get("vector_indexed_families", []),
            "empty_approved_families": report.get("empty_approved_families", []),
            "deferred_families": report.get("deferred_families", []),
            "memory_substrate_status": report.get("memory_substrate_status"),
        },
        "advisory_only": True,
        "makes_determination": False,
        "metadata_only": True,
        "guardrails": {
            "read_only": True,
            "no_raw": True,
            "no_external_writeback": True,
            "advisory_only": True,
            "no_determination": True,
            "no_readiness_overstatement": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(closeout, indent=2, default=str)
        _assert_no_raw(serialized, "coverage-parity closeout json")
        (out_dir / _CLOSEOUT_JSON).write_text(serialized + "\n", encoding="utf-8")
        md = _render_closeout_md(closeout)
        _assert_no_raw(md, "coverage-parity closeout markdown")
        (out_dir / _CLOSEOUT_MD).write_text(md, encoding="utf-8")
        closeout["proof_path"] = str(out_dir / _CLOSEOUT_JSON)
        closeout["proof_md_path"] = str(out_dir / _CLOSEOUT_MD)

    return closeout


def _render_closeout_md(c: dict[str, Any]) -> str:
    rep = c["coverage_parity"]
    planes = c["planes"]
    lines = [
        "# Phase 09 — Coverage Parity Closeout",
        "",
        f"- closeout_ok: {c['closeout_ok']}",
        f"- generated_utc: {c['generated_utc']}",
        f"- coverage_parity_ok: {rep.get('coverage_parity_ok')}",
        f"- deterministic_allowlisted_family_count: {rep.get('deterministic_allowlisted_family_count')}",
        f"- deterministic_reader_family_count: {rep.get('deterministic_reader_family_count')}",
        f"- approved_manifest_family_count: {rep.get('approved_manifest_family_count')}",
        f"- vector_indexed_family_count: {rep.get('vector_indexed_family_count')}",
        f"- missing_reader_families: {rep.get('missing_reader_families')}",
        f"- empty_approved_families: {planes.get('empty_approved_families')}",
        f"- deferred_families: {planes.get('deferred_families')}",
        f"- memory_substrate_status: {planes.get('memory_substrate_status')}",
        "",
        "## Sub-proofs",
        "",
    ]
    lines += [f"- {k}: {v}" for k, v in c["sub_proofs_passed"].items()]
    lines += [
        "",
        "## Coverage planes",
        "",
        f"- reader-backed: {planes.get('deterministic_reader_families')}",
        f"- manifest-approved: {planes.get('approved_manifest_families')}",
        f"- vector-indexed: {planes.get('vector_indexed_families')}",
        "",
    ]
    return "\n".join(lines)
