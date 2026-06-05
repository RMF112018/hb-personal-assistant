"""Phase 09 Prompt 29 — hallucination risk checks (advisory measurement).

A read-only, advisory measurement over the deterministic retrieval corpus that scores **hallucination-risk
and overconfidence indicators** — how risky the corpus is to present as fact — for human awareness. It
**makes no determination and blocks nothing**; it scores risk and bands it.

Hallucination-risk indicators: unsupported claims (fabrication, via Prompt 28's
``detect_and_route_claims``), tier-3 items presented as fact, stale/conflict items, coverage gaps, and the
broker degradation mode. Overconfidence indicators: high confidence assigned to weakly-grounded items
(tier-3 / unsupported / stale-or-conflict), and a high-confidence-tier-3 mismatch count. A deterministic
``risk_band`` (low/medium/high) is derived with an ``indicators`` list of the firing signals.

Read-only and advisory: ``assembles_final_answer`` is always ``False``, ``makes_determination`` is always
``False``, and the builder **persists nothing** (no DB writes). Fail-closed on missing policy or stale
schema. Metadata-only: counts, bucketed bands, distributions, family names, indicator flags — no raw
content/source ref.

Public entry points:
  assess_hallucination_risk(envelope, *, seed=None) -> dict
  build_hallucination_risk_checks(db_path=None, *, project_key=None, families=None) -> dict
  build_hallucination_risk_checks_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain retrieval hallucination-risk build | proof --json
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy

from ..financial_review_routing import _assert_no_raw
from .broker import RetrievalBroker
from .models import RetrievalEnvelope, RetrievalItem
from .policy import EXCLUDED_FAMILIES
from .unsupported_claim_checks import detect_and_route_claims

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "hallucination-risk-checks-proof.json"
_PROOF_MD = "hallucination-risk-checks-proof.md"

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_hallucination_risk_checks.seed.yaml"


class HallucinationRiskError(RuntimeError):
    """Raised when the hallucination-risk builder cannot resolve policy/schema (fail-closed)."""


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


def _open_ro(db_path: str | None) -> sqlite3.Connection | None:
    resolved = db_path or str(PathPolicy().get_db_path())
    try:
        return sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None


def _schema_ready(db_path: str | None) -> int:
    """Return the schema version if ready (>=38), else raise fail-closed."""
    conn = _open_ro(db_path)
    if conn is None:
        raise HallucinationRiskError("schema not ready for hallucination risk checks (no database)")
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        if row is None:
            raise HallucinationRiskError("schema not ready (no schema_migrations)")
        ver_row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(ver_row[0]) if ver_row and ver_row[0] is not None else 0
        if version < 38:
            raise HallucinationRiskError(
                f"schema not ready for hallucination risk checks (version {version}, expected >= 38)"
            )
    finally:
        conn.close()
    return version


def load_hallucination_risk_checks_contract() -> dict[str, Any]:
    """Load the hallucination-risk-checks contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("hallucination_risk_checks_contract")
    if not isinstance(contract, dict) or "risk_bands" not in contract:
        raise HallucinationRiskError(
            "phase 09 hallucination-risk-checks contract not found or missing required fields"
        )
    return contract


def load_hallucination_risk_checks_seed() -> dict[str, Any]:
    """Load the resolved hallucination-risk-checks seed (fail-closed if missing/invalid)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    if not candidate.exists():
        raise HallucinationRiskError(f"hallucination-risk-checks seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "high_overconfidence_rate" not in data:
        raise HallucinationRiskError(
            f"{candidate} must define the hallucination-risk-checks policy"
        )
    return data


def _share_band(frac: float) -> str:
    if frac <= 0.0:
        return "0.00"
    if frac >= 1.0:
        return "1.00"
    if frac <= 0.25:
        return "0.01-0.25"
    if frac <= 0.50:
        return "0.26-0.50"
    if frac <= 0.75:
        return "0.51-0.75"
    return "0.76-0.99"


def _is_unsupported(it: RetrievalItem) -> bool:
    return not (
        bool(it.source_ref) and bool(it.source_family) and it.source_family not in EXCLUDED_FAMILIES
    )


def assess_hallucination_risk(
    envelope: RetrievalEnvelope, *, seed: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Score hallucination-risk + overconfidence indicators over a RetrievalEnvelope (metadata-only).

    Returns counts, bucketed bands, distributions, a deterministic ``risk_band`` (low/medium/high), and an
    ``indicators`` list of the firing signals. Makes no determination and blocks nothing.
    """
    if seed is None:
        seed = load_hallucination_risk_checks_seed()
    high_overconf = float(seed.get("high_overconfidence_rate", 0.25))
    high_tier3 = float(seed.get("high_tier3_share", 0.50))

    items = list(envelope.items)
    n = len(items)
    cc = detect_and_route_claims(items)
    unsupported = int(cc["unsupported_count"])

    tier3 = sum(1 for it in items if int(it.review_tier) >= 3)
    stale = sum(1 for it in items if it.stale_unknown_flags)
    conflict = sum(1 for it in items if it.conflict_flags)
    confidence_distribution: dict[str, int] = {}
    overconfident = 0
    high_conf_tier3 = 0
    for it in items:
        cls = (it.confidence_class or "unknown").lower()
        confidence_distribution[cls] = confidence_distribution.get(cls, 0) + 1
        if cls == "high":
            weakly_grounded = (
                int(it.review_tier) >= 3
                or _is_unsupported(it)
                or bool(it.stale_unknown_flags)
                or bool(it.conflict_flags)
            )
            if weakly_grounded:
                overconfident += 1
            if int(it.review_tier) >= 3:
                high_conf_tier3 += 1

    def _rate(x: int) -> float:
        return (x / n) if n else 0.0

    unsupported_rate = _rate(unsupported)
    overconfidence_rate = _rate(overconfident)
    tier3_share = _rate(tier3)
    coverage_gap = bool(envelope.coverage_warnings)
    degradation_mode = str(envelope.degradation_mode)

    indicators: list[str] = []
    if unsupported > 0:
        indicators.append("unsupported_claims")
    if tier3_share > high_tier3:
        indicators.append("tier3_presented_as_fact")
    if stale > 0 or conflict > 0:
        indicators.append("stale_or_conflict")
    if coverage_gap:
        indicators.append("coverage_gap")
    if degradation_mode in ("blocked", "narrow_claims"):
        indicators.append("degradation")
    if overconfident > 0:
        indicators.append("overconfidence")
    if high_conf_tier3 > 0:
        indicators.append("high_confidence_tier3")

    if unsupported > 0 or degradation_mode == "blocked" or overconfidence_rate > high_overconf:
        risk_band = "high"
    elif (
        overconfident > 0
        or tier3_share > high_tier3
        or stale > 0
        or conflict > 0
        or degradation_mode == "narrow_claims"
        or coverage_gap
    ):
        risk_band = "medium"
    else:
        risk_band = "low"

    return {
        "claim_count": n,
        "risk_band": risk_band,
        "indicators": indicators,
        "hallucination_indicators": {
            "unsupported_count": unsupported,
            "unsupported_rate_band": _share_band(unsupported_rate),
            "tier3_count": tier3,
            "tier3_share_band": _share_band(tier3_share),
            "stale_count": stale,
            "stale_share_band": _share_band(_rate(stale)),
            "conflict_count": conflict,
            "conflict_share_band": _share_band(_rate(conflict)),
            "coverage_gap": coverage_gap,
            "degradation_mode": degradation_mode,
        },
        "overconfidence_indicators": {
            "overconfident_count": overconfident,
            "overconfidence_rate_band": _share_band(overconfidence_rate),
            "high_confidence_tier3_count": high_conf_tier3,
            "confidence_distribution": confidence_distribution,
        },
        "tier_distribution": dict(envelope.tier_distribution),
    }


def build_hallucination_risk_checks(
    db_path: str | None = None,
    *,
    project_key: str | None = None,
    families: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Measure hallucination risk + overconfidence over the deterministic corpus (read-only, advisory).

    Returns a JSON-safe, metadata-only summary (counts, bands, distributions, risk band, indicators —
    never raw content/source ref); persists nothing. Makes no determination and blocks nothing.
    """
    contract = load_hallucination_risk_checks_contract()
    seed = load_hallucination_risk_checks_seed()
    schema_version = _schema_ready(db_path)

    env = RetrievalBroker(db_path).retrieve(
        project_key=project_key, families=families, emit_receipt=False
    )
    assessment = assess_hallucination_risk(env, seed=seed)
    status = "built" if assessment["claim_count"] else "empty"

    return {
        "command": "second-brain retrieval hallucination-risk build",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": status,
        "schema_version": schema_version,
        "project_key": project_key,
        "claim_count": assessment["claim_count"],
        "risk_band": assessment["risk_band"],
        "indicators": assessment["indicators"],
        "hallucination_indicators": assessment["hallucination_indicators"],
        "overconfidence_indicators": assessment["overconfidence_indicators"],
        "tier_distribution": assessment["tier_distribution"],
        "coverage_warnings": list(env.coverage_warnings),
        "advisory_only": True,
        "assembles_final_answer": False,
        "makes_determination": False,
        "blocks_nothing": True,
        "policy_version": seed.get("version"),
        "contract_version": contract.get("version"),
        "read_only": True,
    }


# --- Proof ---------------------------------------------------------------------------------------


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Hallucination Risk Checks Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- risk_band: {proof['risk_band']} (must be high on the synthetic set)",
        f"- unsupported_count: {proof['unsupported_count']} (must be >= 1)",
        f"- overconfident_count: {proof['overconfident_count']} (must be >= 1)",
        f"- indicators: {proof['indicators']}",
        f"- fabrication_indicator_present: {proof['fabrication_indicator_present']}",
        f"- overconfidence_indicator_present: {proof['overconfidence_indicator_present']}",
        f"- makes_determination: {proof['makes_determination']} (must be false)",
        f"- assembles_final_answer: {proof['assembles_final_answer']} (must be false)",
        f"- build_path_no_db_writes: {proof['build_path_no_db_writes']} (must be true)",
        f"- no_raw_emitted: {proof['no_raw_emitted']} (must be true)",
        "",
    ]
    return "\n".join(lines)


def _synthetic_envelope() -> RetrievalEnvelope:
    """A corpus exposing each indicator: a clean supported tier-1 high-confidence item (low risk); an
    overconfident item (high confidence + tier 3); an unsupported item (no source ref); a conflict-flagged
    item — under a degraded, coverage-gapped envelope."""
    items = [
        RetrievalItem(
            source_family="approved_obsidian_generated_outputs",
            source_ref="ref-clean",
            record_type="note",
            record_ref="c",
            confidence_class="high",
            review_tier=1,
        ),
        RetrievalItem(
            source_family="accepted_long_term_memory",
            source_ref="ref-overconf",
            record_type="memory",
            record_ref="o",
            confidence_class="high",
            review_tier=3,  # high confidence on a mandatory-review item -> overconfidence
        ),
        RetrievalItem(
            source_family="project_issue_history_items",
            source_ref="",  # no source link -> unsupported (fabrication risk)
            record_type="issue",
            record_ref="u",
            confidence_class="medium",
            review_tier=2,
        ),
        RetrievalItem(
            source_family="cross_source_relationships",
            source_ref="ref-conflict",
            record_type="relationship",
            record_ref="x",
            confidence_class="low",
            review_tier=2,
            conflict_flags=["conflicting_relationship_state"],
        ),
    ]
    return RetrievalEnvelope(
        items=items,
        degradation_mode="narrow_claims",
        tier_distribution={"1": 1, "2": 2, "3": 1},
        coverage_warnings=["no_results_for_family:aging_exposure_report_items"],
    )


def build_hallucination_risk_checks_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: each risk + overconfidence indicator fires on the synthetic corpus, the risk band
    is high, no determination is made, the build path performs no DB writes, and no raw is emitted."""
    import tempfile

    from .vector_index import _proof_db

    env = _synthetic_envelope()
    assessment = assess_hallucination_risk(env)

    fabrication = "unsupported_claims" in assessment["indicators"]
    overconfidence = "overconfidence" in assessment["indicators"]

    with tempfile.TemporaryDirectory() as tmp:
        db = _proof_db(tmp)
        before = _total_rows(db)
        build_result = build_hallucination_risk_checks(db)
        after = _total_rows(db)
    build_path_no_db_writes = before == after

    serialized = json.dumps(assessment, default=str) + json.dumps(build_result, default=str)
    no_raw_emitted = "ref-" not in serialized and "content_excerpt" not in serialized

    proof_passed = (
        assessment["risk_band"] == "high"
        and int(assessment["hallucination_indicators"]["unsupported_count"]) >= 1
        and int(assessment["overconfidence_indicators"]["overconfident_count"]) >= 1
        and fabrication
        and overconfidence
        and build_result["makes_determination"] is False
        and build_result["assembles_final_answer"] is False
        and build_path_no_db_writes
        and no_raw_emitted
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_hallucination_risk_checks",
        "command": "second-brain retrieval hallucination-risk proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "risk_band": assessment["risk_band"],
        "unsupported_count": assessment["hallucination_indicators"]["unsupported_count"],
        "overconfident_count": assessment["overconfidence_indicators"]["overconfident_count"],
        "indicators": assessment["indicators"],
        "fabrication_indicator_present": fabrication,
        "overconfidence_indicator_present": overconfidence,
        "makes_determination": build_result["makes_determination"],
        "assembles_final_answer": build_result["assembles_final_answer"],
        "build_path_no_db_writes": build_path_no_db_writes,
        "no_raw_emitted": no_raw_emitted,
        "metadata_only": True,
        "guardrails": {
            "advisory_only": True,
            "no_final_answer": True,
            "no_determination": True,
            "no_blocking": True,
            "no_raw": True,
            "no_external_writeback": True,
            "local_first": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(out, "hallucination risk checks proof json")
        (out_dir / _PROOF_JSON).write_text(out + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "hallucination risk checks proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof


def _total_rows(db_path: str) -> int:
    """Sum of row counts across all user tables — a stable no-mutation signal (not file size)."""
    conn = sqlite3.connect(db_path)
    try:
        tables = [
            str(r[0])
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        return sum(int(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]) for t in tables)
    finally:
        conn.close()
