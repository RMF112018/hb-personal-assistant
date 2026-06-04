"""Phase 09 Prompt 14 — embedding + vector-store policy and no-raw guardrails (read-only).

Defines and enforces the policy that governs the Phase 09 semantic-retrieval plane: which source
families may be embedded (the redacted, source-linked read models — never an ``EXCLUDED_FAMILIES`` raw
family), the allowed embedding providers / vector stores / embedding dimensions, the required
metadata-only node fields, and the persistence rules (vectors are never persisted to SQLite; the ledger
is metadata-only and the ``raw_vector_content_persisted`` guard CHECK(=0) enforces it).

The core primitive is :func:`validate_embedding_candidate` — a fail-closed no-raw guardrail that, given
a candidate node's metadata, returns the policy violations (empty ⇒ safe to embed). It rejects
non-embeddable / excluded families, missing required metadata, forbidden raw reference fields, raw
content / secret / signed-URL shapes (via the shared ``_FORBIDDEN`` scanner), embedding/vector blobs,
and unresolved review-required items. No embeddings are computed and no index is built here.

Everything is local-only, metadata-only, read-only (the status probe opens the DB ``?mode=ro`` and
never writes), and fail-closed (a missing/invalid contract or seed raises ``EmbeddingVectorPolicyError``).

Public entry points:
  load_embedding_vector_policy_contract() -> dict
  load_embedding_vector_policy_seed() -> dict
  embeddable_families(seed) -> list[str]
  validate_embedding_candidate(candidate, *, contract, seed) -> list[str]
  build_embedding_vector_policy_status(db_path=None) -> dict
  build_no_raw_vector_policy_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain retrieval embedding-policy status|no-raw-proof --json
"""

from __future__ import annotations

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
from .policy import ALLOWLISTED_SOURCE_FAMILIES, EXCLUDED_FAMILIES

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_embedding_vector_policy.seed.yaml"
SEED_ENV_VAR = "HB_SECOND_BRAIN_EMBEDDING_VECTOR_POLICY"

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "embedding-vector-policy-no-raw-proof.json"
_PROOF_MD = "embedding-vector-policy-no-raw-proof.md"

# The three V38 retrieval tables this policy governs (metadata-only; vectors live outside SQLite).
_GOVERNED_TABLES = (
    "second_brain_retrieval_embedding_model_evals",
    "second_brain_retrieval_vector_index_runs",
    "second_brain_retrieval_vector_index_items",
)

# Blob keys that must never appear in a candidate's persisted metadata.
_VECTOR_BLOB_FIELDS = ("embedding", "vector", "raw_vector")

# Synthetic forbidden-token shape used only by the no-raw proof's planted-unsafe candidate. Assembled
# at runtime so the literal token never appears in scanned source (the guard must still match it via
# the shared _FORBIDDEN scanner). Never a real secret.
_SYNTHETIC_TOKEN_SHAPE = "Bea" + "rer " + "z" * 32


class EmbeddingVectorPolicyError(RuntimeError):
    """Raised when the embedding/vector policy contract or seed cannot be loaded (fail-closed)."""


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


def load_embedding_vector_policy_contract() -> dict[str, Any]:
    """Load the embedding/vector policy contract (fail-closed if missing/invalid)."""
    contract = load_phase_09_contract("embedding_vector_policy_contract")
    if not isinstance(contract, dict) or "required_node_metadata_fields" not in contract:
        raise EmbeddingVectorPolicyError(
            "phase 09 embedding/vector policy contract not found or missing required fields"
        )
    return contract


def load_embedding_vector_policy_seed() -> dict[str, Any]:
    """Load the resolved embedding/vector policy seed (fail-closed if missing/invalid)."""
    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    env_value = os.environ.get(SEED_ENV_VAR)
    if env_value:
        candidate = Path(env_value).expanduser()
    if not candidate.exists():
        raise EmbeddingVectorPolicyError(f"embedding/vector policy seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "embeddable_source_families" not in data:
        raise EmbeddingVectorPolicyError(f"{candidate} must define the embedding/vector policy")
    return data


def embeddable_families(seed: dict[str, Any]) -> list[str]:
    """Resolve the embeddable allowlist: seed families ∩ broker allowlist − EXCLUDED families."""
    requested = seed.get("embeddable_source_families", []) or []
    return [f for f in requested if f in ALLOWLISTED_SOURCE_FAMILIES and f not in EXCLUDED_FAMILIES]


def validate_embedding_candidate(
    candidate: dict[str, Any], *, contract: dict[str, Any], seed: dict[str, Any]
) -> list[str]:
    """Return policy violations for an embedding candidate (empty ⇒ safe to embed). Fail-closed."""
    violations: list[str] = []
    allowed = set(embeddable_families(seed))

    family = candidate.get("source_family")
    if family in EXCLUDED_FAMILIES:
        violations.append(f"source_family_excluded:{family}")
    elif family not in allowed:
        violations.append(f"source_family_not_embeddable:{family}")

    for field in contract.get("required_node_metadata_fields", []):
        if candidate.get(field) in (None, ""):
            violations.append(f"missing_metadata:{field}")

    forbidden_keys = set(contract.get("forbidden_node_fields", [])) | set(
        FORBIDDEN_REFERENCE_FIELDS
    )
    for key in candidate:
        if key in forbidden_keys:
            violations.append(f"forbidden_field:{key}")
        if key in _VECTOR_BLOB_FIELDS:
            violations.append(f"raw_vector_content:{key}")

    for key, value in candidate.items():
        if isinstance(value, str) and _FORBIDDEN.search(value):
            violations.append(f"raw_content_shape:{key}")

    approved_statuses = set(contract.get("approved_review_statuses", []))
    if candidate.get("review_required") and candidate.get("review_status") not in approved_statuses:
        violations.append("unresolved_review_required")

    return violations


def _open_ro(db_path: str | None) -> sqlite3.Connection | None:
    resolved = db_path or str(PathPolicy().get_db_path())
    try:
        return sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None


def build_embedding_vector_policy_status(db_path: str | None = None) -> dict[str, Any]:
    """Build the read-only embedding/vector policy status report (fail-closed)."""
    contract = load_embedding_vector_policy_contract()
    seed = load_embedding_vector_policy_seed()

    embeddable = embeddable_families(seed)
    config_violations: list[str] = []
    provider = seed.get("embedding_provider")
    if provider not in contract.get("allowed_embedding_providers", []):
        config_violations.append(f"embedding_provider_not_allowed:{provider}")
    if provider in contract.get("deferred_embedding_providers", []):
        config_violations.append(f"embedding_provider_deferred:{provider}")
    vstore = seed.get("vector_store_kind")
    if vstore not in contract.get("allowed_vector_store_kinds", []):
        config_violations.append(f"vector_store_kind_not_allowed:{vstore}")
    dim = seed.get("embedding_dim")
    lo, hi = contract.get("embedding_dim_min"), contract.get("embedding_dim_max")
    if not (isinstance(dim, int) and lo is not None and hi is not None and lo <= dim <= hi):
        config_violations.append(f"embedding_dim_out_of_bounds:{dim}")
    if not embeddable:
        config_violations.append("no_embeddable_families")
    config_valid = not config_violations

    conn = _open_ro(db_path)
    schema_version = 0
    tables_present = False
    governed_rows: dict[str, int] = {}
    if conn is not None:
        try:
            row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            schema_version = int(row[0]) if row and row[0] is not None else 0
            present = []
            for table in _GOVERNED_TABLES:
                exists = (
                    conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                    ).fetchone()
                    is not None
                )
                present.append(exists)
                if exists:
                    governed_rows[table] = int(
                        conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    )
            tables_present = all(present)
        except sqlite3.OperationalError:
            pass
        finally:
            conn.close()

    schema_ready = schema_version >= 38 and tables_present
    blockers: list[str] = []
    if not config_valid:
        blockers.append("config_invalid")
    if not schema_ready:
        blockers.append("schema_not_ready")

    return {
        "command": "second-brain retrieval embedding-policy status",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "policy_loaded": True,
        "policy_version": seed.get("version"),
        "contract_version": contract.get("version"),
        "embedding_provider": provider,
        "embedding_dim": dim,
        "vector_store_kind": vstore,
        "max_nodes_per_run": seed.get("max_nodes_per_run"),
        "embeddable_family_count": len(embeddable),
        "embeddable_families": embeddable,
        "forbidden_family_count": len(EXCLUDED_FAMILIES),
        "deferred_embedding_providers": contract.get("deferred_embedding_providers", []),
        "persistence_rules": contract.get("persistence_rules", {}),
        "config_valid": config_valid,
        "config_violations": config_violations,
        "schema_version": schema_version,
        "schema_version_expected": LATEST_SCHEMA_VERSION,
        "schema_ready": schema_ready,
        "governed_tables": list(_GOVERNED_TABLES),
        "governed_table_rows": governed_rows,
        "blockers": blockers,
        "read_only": True,
    }


def _proof_cases(contract: dict[str, Any], seed: dict[str, Any]) -> list[dict[str, Any]]:
    """Controlled safe + planted-unsafe candidates exercising the no-raw guardrail."""
    safe = {
        "source_family": "phase_07d_source_evidence_trails",
        "source_ref": "evidence_trail:abc123",
        "content_hash": "f" * 64,
        "confidence_class": "deterministic",
        "review_tier": 2,
        "freshness_label": "current",
        "review_required": False,
    }
    planted: list[tuple[str, dict[str, Any]]] = [
        ("excluded_family", {**safe, "source_family": "raw_email_body"}),
        ("non_embeddable_family", {**safe, "source_family": "meeting_prep_brief_sections"}),
        ("raw_body_field", {**safe, "raw_body": "some text"}),
        ("signed_url_field", {**safe, "signed_url": "ref"}),
        ("vector_blob_field", {**safe, "embedding": [0.1, 0.2, 0.3]}),
        (
            "secret_shape_value",
            {**safe, "content_hash": _SYNTHETIC_TOKEN_SHAPE},
        ),
        ("missing_metadata", {k: v for k, v in safe.items() if k != "content_hash"}),
        (
            "unresolved_review",
            {**safe, "review_required": True, "review_status": "review_required"},
        ),
    ]
    cases: list[dict[str, Any]] = []
    safe_violations = validate_embedding_candidate(safe, contract=contract, seed=seed)
    cases.append(
        {
            "name": "safe_candidate",
            "expected_rejected": False,
            "rejected": bool(safe_violations),
            "violations": safe_violations,
            "passed": not safe_violations,
        }
    )
    for name, cand in planted:
        v = validate_embedding_candidate(cand, contract=contract, seed=seed)
        cases.append(
            {
                "name": name,
                "expected_rejected": True,
                "rejected": bool(v),
                "violations": v,
                "passed": bool(v),
            }
        )
    return cases


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Embedding/Vector Policy No-Raw Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- policy_version: {proof['policy_version']}",
        f"- embeddable_family_count: {proof['embeddable_family_count']}",
        "",
        "## Candidate validation cases",
        "",
    ]
    for c in proof["cases"]:
        lines.append(
            f"- [{'ok' if c['passed'] else 'FAIL'}] {c['name']}: "
            f"expected_rejected={c['expected_rejected']} rejected={c['rejected']} "
            f"violations={len(c['violations'])}"
        )
    lines.append("")
    lines.append("## Persistence rules")
    lines.append("")
    for k, v in proof["persistence_rules"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    return "\n".join(lines)


def build_no_raw_vector_policy_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof the no-raw guardrail rejects raw/unsafe candidates (in-memory; no DB writes)."""
    contract = load_embedding_vector_policy_contract()
    seed = load_embedding_vector_policy_seed()
    cases = _proof_cases(contract, seed)
    proof_passed = all(c["passed"] for c in cases)

    proof: dict[str, Any] = {
        "proof": "phase_09_no_raw_embedding_vector_policy",
        "command": "second-brain retrieval embedding-policy no-raw-proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "policy_version": seed.get("version"),
        "embeddable_family_count": len(embeddable_families(seed)),
        "case_count": len(cases),
        "cases": cases,
        "persistence_rules": contract.get("persistence_rules", {}),
        "metadata_only": True,
        "guardrails": {
            "read_only": True,
            "no_raw": True,
            "no_writeback": True,
            "no_raw_vector_content_in_sqlite": True,
            "local_first": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "embedding-vector-policy no-raw proof json")
        (out_dir / _PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "embedding-vector-policy no-raw proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof
