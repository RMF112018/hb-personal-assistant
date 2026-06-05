"""Phase 09 Prompt 15 — approved index source manifests (read-only, fail-closed).

Builds the **approved source manifest** that enumerates which records from three categories may be
semantically indexed: generated outputs (`second_brain_research_packets` and applied, source-linked
`daily_brief_runs`), approved Obsidian outputs (the latest `mode='apply'` `obsidian_index_entries`),
and reviewed memory (`long_term_memory_items`
with `review_status='accepted'`). Only **approved, redacted, source-linked** records enter the manifest;
unresolved high-impact (tier-3 / review_required) items, non-accepted statuses, raw-content shapes, and
non-apply Obsidian manifests are excluded.

The manifest is **metadata-only**: per-family counts + a deterministic `manifest_hash` over the sorted
`family:source_ref_hash:content_hash` of the approved entries. Per-entry refs are hashed, never stored
raw, and the persisted summary row (`second_brain_retrieval_approved_source_manifests`) carries only
counts + hash + a review-tier summary + status. No embeddings are computed and no index is built here.

Everything is local-only, read-only by default (the builder opens the DB `?mode=ro`); persistence is
opt-in (`persist_approved_source_manifest`) and writes a single guard-clean summary row. Fail-closed on
a missing/invalid contract or seed (`ApprovedSourceManifestError`) or a stale schema.

Public entry points:
  load_approved_source_manifest_contract() -> dict
  load_approved_source_manifest_seed() -> dict
  validate_manifest_entry(entry, *, contract) -> list[str]
  build_approved_source_manifest(db_path=None, *, project_key=None) -> dict
  persist_approved_source_manifest(db_path, manifest, *, policy_version) -> str
  build_approved_source_manifest_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain retrieval approved-sources build|proof --json
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

from ..contracts import load_phase_09_contract
from ..corpus_balance_mart import _FORBIDDEN
from ..financial_review_routing import _assert_no_raw
from ..reasoning import FORBIDDEN_REFERENCE_FIELDS
from .policy import EXCLUDED_FAMILIES

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_approved_source_manifest.seed.yaml"
SEED_ENV_VAR = "HB_SECOND_BRAIN_APPROVED_SOURCE_MANIFEST"

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "approved-source-manifest-proof.json"
_PROOF_MD = "approved-source-manifest-proof.md"

_MANIFEST_TABLE = "second_brain_retrieval_approved_source_manifests"
_GENERATED = "generated_outputs"
_OBSIDIAN = "approved_obsidian_outputs"
_MEMORY = "reviewed_memory"
_READ_MODELS = "approved_read_models"


class ApprovedSourceManifestError(RuntimeError):
    """Raised when the approved-source-manifest contract or seed cannot be loaded (fail-closed)."""


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


def load_approved_source_manifest_contract() -> dict[str, Any]:
    """Load the approved-source-manifest contract (fail-closed if missing/invalid)."""
    contract = load_phase_09_contract("approved_source_manifest_contract")
    if not isinstance(contract, dict) or "manifest_categories" not in contract:
        raise ApprovedSourceManifestError(
            "phase 09 approved-source-manifest contract not found or missing required fields"
        )
    return contract


def load_approved_source_manifest_seed() -> dict[str, Any]:
    """Load the resolved approved-source-manifest seed (fail-closed if missing/invalid)."""
    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    env_value = os.environ.get(SEED_ENV_VAR)
    if env_value:
        candidate = Path(env_value).expanduser()
    if not candidate.exists():
        raise ApprovedSourceManifestError(f"approved-source-manifest seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "enabled_categories" not in data:
        raise ApprovedSourceManifestError(f"{candidate} must define the manifest config")
    return data


def validate_manifest_entry(entry: dict[str, Any], *, contract: dict[str, Any]) -> list[str]:
    """Return approval violations for a candidate entry (empty ⇒ approved). Fail-closed.

    Excludes raw families, excluded/unresolved review statuses, unresolved high-impact (tier-3 or
    review_required with status != accepted), missing required metadata, forbidden raw fields, and any
    raw-content / secret / URL shapes.
    """
    violations: list[str] = []

    family = entry.get("source_family")
    if family in EXCLUDED_FAMILIES:
        violations.append(f"excluded_family:{family}")

    status = entry.get("review_status")
    approved = set(contract.get("approved_review_statuses", []))
    excluded = set(contract.get("excluded_review_statuses", []))
    if status in excluded:
        violations.append(f"excluded_review_status:{status}")
    elif status not in approved:
        violations.append(f"unapproved_review_status:{status}")

    tier = entry.get("review_tier")
    max_tier = contract.get("max_auto_approval_review_tier", 2)
    high_impact_unresolved = bool(entry.get("review_required")) or (
        isinstance(tier, int) and tier > max_tier
    )
    if high_impact_unresolved and status != "accepted":
        violations.append("unresolved_high_impact")

    for field in contract.get("required_entry_metadata", []):
        if entry.get(field) in (None, ""):
            violations.append(f"missing_metadata:{field}")

    forbidden_keys = set(contract.get("forbidden_entry_fields", [])) | set(
        FORBIDDEN_REFERENCE_FIELDS
    )
    for key, value in entry.items():
        if key in forbidden_keys:
            violations.append(f"forbidden_field:{key}")
        if isinstance(value, str) and _FORBIDDEN.search(value):
            violations.append(f"raw_content_shape:{key}")

    return violations


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


def _read_generated(conn: sqlite3.Connection, project_key: str | None, limit: int) -> list[dict]:
    out: list[dict] = []
    if _table_exists(conn, "second_brain_research_packets"):
        clause = " AND project_key = ?" if project_key is not None else ""
        params: list[Any] = ["accepted"]
        if project_key is not None:
            params.append(project_key)
        rows = conn.execute(
            "SELECT packet_id, topic_hash, confidence_class, review_tier, review_status "
            "FROM second_brain_research_packets WHERE review_status = ?" + clause + " LIMIT ?",
            (*params, limit),
        ).fetchall()
        for packet_id, topic_hash, conf, tier, status in rows:
            out.append(
                {
                    "source_family": _GENERATED,
                    "source_ref": str(packet_id),
                    "source_ref_hash": _hash(str(packet_id)),
                    "content_hash": str(topic_hash or _hash(str(packet_id))),
                    "review_tier": int(tier) if tier is not None else 1,
                    "review_status": str(status or "accepted"),
                    "confidence_class": str(conf or "unknown"),
                    "freshness_label": "current",
                    "review_required": (int(tier) if tier is not None else 1) >= 3,
                }
            )
    if _table_exists(conn, "daily_brief_runs") and len(out) < limit:
        params = ["apply", "blocked"]
        if project_key is not None:
            # daily_brief_runs has no project_key column. Project-specific filtering for generated
            # daily briefs is therefore unsupported until the table shape changes.
            return out
        rows = conn.execute(
            "SELECT brief_run_id, output_path_hash, review_tier, status "
            "FROM daily_brief_runs WHERE mode = ? AND status != ? "
            "AND output_path_hash IS NOT NULL AND source_ref_count > 0 "
            "ORDER BY generated_utc DESC, brief_run_id DESC LIMIT ?",
            (*params, limit - len(out)),
        ).fetchall()
        for brief_run_id, content_hash, tier, status in rows:
            resolved_tier = int(tier) if tier is not None else 1
            out.append(
                {
                    "source_family": _GENERATED,
                    "source_ref": str(brief_run_id),
                    "source_ref_hash": _hash(str(brief_run_id)),
                    "content_hash": str(content_hash or _hash(str(brief_run_id))),
                    "review_tier": resolved_tier,
                    "review_status": "auto_advisory",
                    "confidence_class": "high",
                    "freshness_label": "current",
                    "review_required": resolved_tier >= 3,
                    "generated_output_kind": "daily_brief",
                    "generated_output_status": str(status or "assembled"),
                }
            )
    return out


def _read_obsidian(conn: sqlite3.Connection, project_key: str | None, limit: int) -> list[dict]:
    if not _table_exists(conn, "obsidian_index_entries") or not _table_exists(
        conn, "obsidian_index_manifests"
    ):
        return []
    row = conn.execute(
        "SELECT manifest_id FROM obsidian_index_manifests "
        "WHERE mode = 'apply' ORDER BY generated_utc DESC, manifest_id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return []
    clause = " AND project_key = ?" if project_key is not None else ""
    params: list[Any] = [row[0]]
    if project_key is not None:
        params.append(project_key)
    entries = conn.execute(
        "SELECT note_path_hash, content_hash, confidence_class, review_status, source_refs_json "
        "FROM obsidian_index_entries WHERE manifest_id = ?" + clause + " LIMIT ?",
        (*params, limit),
    ).fetchall()
    out: list[dict] = []
    for note_hash, content_hash, conf, status, refs_json in entries:
        tier = 1
        try:
            meta = json.loads(refs_json) if refs_json else {}
            tier = int(meta.get("review_tier", 1))
        except Exception:
            tier = 1
        out.append(
            {
                "source_family": _OBSIDIAN,
                "source_ref": str(note_hash),
                "source_ref_hash": _hash(str(note_hash)),
                "content_hash": str(content_hash or ""),
                "review_tier": tier,
                "review_status": str(
                    status or ("review_required" if tier == 3 else "auto_advisory")
                ),
                "confidence_class": str(conf or "high"),
                "freshness_label": "current",
                "review_required": tier >= 3,
            }
        )
    return out


def _read_memory(conn: sqlite3.Connection, project_key: str | None, limit: int) -> list[dict]:
    if not _table_exists(conn, "long_term_memory_items"):
        return []
    clause = " AND project_key = ?" if project_key is not None else ""
    params: list[Any] = ["accepted"]
    if project_key is not None:
        params.append(project_key)
    rows = conn.execute(
        "SELECT memory_id, confidence_class, review_status "
        "FROM long_term_memory_items WHERE review_status = ?" + clause + " LIMIT ?",
        (*params, limit),
    ).fetchall()
    out: list[dict] = []
    for memory_id, conf, status in rows:
        out.append(
            {
                "source_family": _MEMORY,
                "source_ref": str(memory_id),
                "source_ref_hash": _hash(str(memory_id)),
                "content_hash": _hash(str(memory_id)),
                "review_tier": 1,
                "review_status": str(status or "accepted"),
                "confidence_class": str(conf or "unknown"),
                "freshness_label": "current",
                "review_required": False,
            }
        )
    return out


def _read_read_models(db_path: str | None, project_key: str | None, limit: int) -> list[dict]:
    """Eligible deterministic read-model items (shared loader) → manifest candidate entries.

    Reuses ``read_model_loader.load_approved_read_model_nodes`` so the manifest's approved set is exactly
    what the vector-index gather will index. Entries carry hashes/labels only — never the redacted
    excerpt text itself (``content_excerpt_redacted`` is a forbidden entry field).
    """
    from .read_model_loader import load_approved_read_model_nodes

    out: list[dict] = []
    for node in load_approved_read_model_nodes(db_path, project_key=project_key)[:limit]:
        out.append(
            {
                "source_family": str(node["source_family"]),
                "source_ref": str(node["source_ref"]),
                "source_ref_hash": _hash(str(node["source_ref"])),
                "content_hash": str(node["content_hash"]),
                "review_tier": int(node["review_tier"]),
                "review_status": str(node["review_status"]),
                "confidence_class": str(node["confidence_class"]),
                "freshness_label": str(node["freshness_label"]),
                "review_required": bool(node["review_required"]),
            }
        )
    return out


def _read_candidates(
    conn: sqlite3.Connection,
    seed: dict[str, Any],
    project_key: str | None,
    db_path: str | None,
) -> dict[str, list[dict]]:
    enabled = set(seed.get("enabled_categories", []))
    limit = int(seed.get("max_refs_per_category", 2000))
    candidates: dict[str, list[dict]] = {}
    if _GENERATED in enabled:
        candidates[_GENERATED] = _read_generated(conn, project_key, limit)
    if _OBSIDIAN in enabled:
        candidates[_OBSIDIAN] = _read_obsidian(conn, project_key, limit)
    if _MEMORY in enabled:
        candidates[_MEMORY] = _read_memory(conn, project_key, limit)
    if _READ_MODELS in enabled:
        candidates[_READ_MODELS] = _read_read_models(db_path, project_key, limit)
    return candidates


def _tier_summary(entries: list[dict]) -> str:
    tiers = sorted({int(e["review_tier"]) for e in entries})
    if not tiers:
        return "none"
    return "max=%d;tiers=%s" % (max(tiers), ",".join(str(t) for t in tiers))


def build_approved_source_manifest(
    db_path: str | None = None, *, project_key: str | None = None
) -> dict[str, Any]:
    """Build the approved source manifest (read-only, fail-closed). Returns the manifest dict."""
    contract = load_approved_source_manifest_contract()
    seed = load_approved_source_manifest_seed()

    conn = _open_ro(db_path)
    schema_version = 0
    schema_ready = False
    families: dict[str, dict[str, Any]] = {}
    approved_entries: list[dict] = []
    try:
        if conn is not None and _table_exists(conn, "schema_migrations"):
            row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            schema_version = int(row[0]) if row and row[0] is not None else 0
            schema_ready = schema_version >= 38 and _table_exists(conn, _MANIFEST_TABLE)
            if schema_ready:
                candidates = _read_candidates(conn, seed, project_key, db_path)
                for family, items in candidates.items():
                    fam_approved: list[dict] = []
                    fam_excluded = 0
                    reasons: dict[str, int] = {}
                    for entry in items:
                        violations = validate_manifest_entry(entry, contract=contract)
                        if violations:
                            fam_excluded += 1
                            for v in violations:
                                reasons[v.split(":")[0]] = reasons.get(v.split(":")[0], 0) + 1
                        else:
                            fam_approved.append(entry)
                    approved_entries.extend(fam_approved)
                    families[family] = {
                        "candidate_count": len(items),
                        "approved_count": len(fam_approved),
                        "excluded_count": fam_excluded,
                        "exclude_reasons": reasons,
                    }
    finally:
        if conn is not None:
            conn.close()

    if not schema_ready:
        raise ApprovedSourceManifestError(
            f"schema not ready for approved-source manifest (version {schema_version}, expected >= 38)"
        )

    manifest_hash = _hash(
        "|".join(
            sorted(
                f"{e['source_family']}:{e['source_ref_hash']}:{e['content_hash']}"
                for e in approved_entries
            )
        )
    )
    approved_ref_count = len(approved_entries)
    approved_family_count = sum(1 for f in families.values() if f["approved_count"] > 0)
    warnings: list[str] = []
    if approved_ref_count == 0:
        warnings.append("no_approved_sources")
    for family, stats in families.items():
        if stats["approved_count"] == 0:
            warnings.append(f"empty_family:{family}")

    return {
        "command": "second-brain retrieval approved-sources build",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "policy_loaded": True,
        "policy_version": seed.get("version"),
        "contract_version": contract.get("version"),
        "manifest_id": f"asm_{manifest_hash[:32]}",
        "manifest_hash": manifest_hash,
        "schema_version": schema_version,
        "schema_version_expected": LATEST_SCHEMA_VERSION,
        "approved_family_count": approved_family_count,
        "approved_ref_count": approved_ref_count,
        "review_tier_summary": _tier_summary(approved_entries),
        "status": "approved" if approved_ref_count > 0 else "empty",
        "families": families,
        "warnings": warnings,
        "read_only": True,
    }


def persist_approved_source_manifest(
    db_path: str | None, manifest: dict[str, Any], *, policy_version: str
) -> str:
    """Persist a single guard-clean summary row to the manifest table. Returns manifest_id."""
    resolved = db_path or str(PathPolicy().get_db_path())
    manifest_id = str(manifest["manifest_id"])
    conn = sqlite3.connect(resolved)
    try:
        conn.execute(
            f"INSERT OR REPLACE INTO {_MANIFEST_TABLE} "
            "(manifest_id, policy_version, schema_version, manifest_hash, approved_family_count, "
            "approved_ref_count, review_tier, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                manifest_id,
                policy_version,
                int(manifest["schema_version"]),
                str(manifest["manifest_hash"]),
                int(manifest["approved_family_count"]),
                int(manifest["approved_ref_count"]),
                str(manifest["review_tier_summary"]),
                str(manifest["status"]),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return manifest_id


def _proof_cases(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Controlled safe + planted-unsafe entries exercising the approval/no-raw guardrail."""

    def _safe(family: str) -> dict[str, Any]:
        return {
            "source_family": family,
            "source_ref": f"{family}:ref-1",
            "content_hash": "f" * 64,
            "review_tier": 1,
            "review_status": "accepted",
            "confidence_class": "deterministic",
            "review_required": False,
        }

    # A synthetic forbidden token shape, assembled at runtime so no literal token is in source.
    synthetic_secret = "Bea" + "rer " + "z" * 32
    planted: list[tuple[str, dict[str, Any]]] = [
        ("excluded_family", {**_safe(_GENERATED), "source_family": "raw_email_body"}),
        ("excluded_review_status", {**_safe(_GENERATED), "review_status": "rejected"}),
        ("pending_review_status", {**_safe(_OBSIDIAN), "review_status": "pending_review"}),
        (
            "unresolved_high_impact",
            {
                **_safe(_OBSIDIAN),
                "review_tier": 3,
                "review_required": True,
                "review_status": "review_required",
            },
        ),
        ("missing_metadata", {k: v for k, v in _safe(_MEMORY).items() if k != "content_hash"}),
        ("forbidden_field", {**_safe(_GENERATED), "raw_body": "x"}),
        ("raw_content_shape", {**_safe(_MEMORY), "content_hash": synthetic_secret}),
    ]
    cases: list[dict[str, Any]] = []
    for family in (_GENERATED, _OBSIDIAN, _MEMORY):
        v = validate_manifest_entry(_safe(family), contract=contract)
        cases.append(
            {
                "name": f"safe_{family}",
                "expected_approved": True,
                "approved": not v,
                "violations": v,
                "passed": not v,
            }
        )
    for name, entry in planted:
        v = validate_manifest_entry(entry, contract=contract)
        cases.append(
            {
                "name": name,
                "expected_approved": False,
                "approved": not v,
                "violations": v,
                "passed": bool(v),
            }
        )
    return cases


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Approved Source Manifest Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- policy_version: {proof['policy_version']}",
        "",
        "## Approval / no-raw guardrail cases",
        "",
    ]
    for c in proof["cases"]:
        lines.append(
            f"- [{'ok' if c['passed'] else 'FAIL'}] {c['name']}: "
            f"expected_approved={c['expected_approved']} approved={c['approved']} "
            f"violations={len(c['violations'])}"
        )
    lines.append("")
    return "\n".join(lines)


def build_approved_source_manifest_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof the approval/no-raw guardrail excludes unsafe candidates (in-memory)."""
    contract = load_approved_source_manifest_contract()
    seed = load_approved_source_manifest_seed()
    cases = _proof_cases(contract)
    proof_passed = all(c["passed"] for c in cases)

    proof: dict[str, Any] = {
        "proof": "phase_09_approved_source_manifest",
        "command": "second-brain retrieval approved-sources proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "policy_version": seed.get("version"),
        "case_count": len(cases),
        "cases": cases,
        "metadata_only": True,
        "guardrails": {
            "read_only": True,
            "no_raw": True,
            "no_writeback": True,
            "exclude_unresolved_high_impact": True,
            "only_approved_obsidian_apply_manifests": True,
            "local_first": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "approved-source-manifest proof json")
        (out_dir / _PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "approved-source-manifest proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof
