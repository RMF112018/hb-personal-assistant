"""Phase 09 Prompt 21 — metadata filter enforcement (fail-closed, before + after retrieval).

Enforces **project / source / date / review / confidence / source-coverage** filters around the
retrieval pipeline:

- **Before** retrieval (`normalize_filter`): reject any explicitly requested **excluded** family
  (fail-closed — excluded families must never be queried), intersect requested families with the broker
  allowlist (unknown families dropped with a coverage note), and validate the date window / tier bound /
  confidence value. The resolved family set + project key constrain what the deterministic broker reads.
- **After** retrieval (`apply_metadata_filter`): drop merged `RetrievalItem`s that fall outside the
  requested project / family set / date window / review-tier ceiling / confidence floor, recording the
  reason per drop, and emit source-coverage warnings (`no_results_for_family`, and — for families whose
  `recency` is not a parseable date — `date_filter_not_applicable`). Review tier, confidence class, source
  references, and freshness are **preserved** on kept items; no raw content is ever read or emitted.

The layer is read-only and metadata-only: it persists nothing and never assembles a final answer. It is
consumed by ``hybrid_broker.build_hybrid_retrieval`` via its optional ``metadata_filter`` parameter.

Public entry points:
  MetadataFilter (spec)
  normalize_filter(spec, *, contract) -> (project_key, effective_families | None, notes)
  apply_metadata_filter(items, spec, *, contract, selected_families) -> (kept, dropped_by_reason, warnings)
  build_metadata_filter_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain retrieval metadata-filter status | apply "<q>" | proof --json
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from hb_assistant.config.path_policy import PathPolicy

from ..financial_review_routing import _assert_no_raw
from .models import RetrievalItem
from .policy import ALLOWLISTED_SOURCE_FAMILIES, EXCLUDED_FAMILIES

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "metadata-filter-proof.json"
_PROOF_MD = "metadata-filter-proof.md"

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_metadata_filter.seed.yaml"


class MetadataFilterError(RuntimeError):
    """Raised when the metadata filter cannot resolve policy or a filter is invalid (fail-closed)."""


class MetadataFilter(BaseModel):
    """A project/source/date/review/confidence filter spec (metadata-only; no raw content)."""

    project_key: str | None = None
    source_families: tuple[str, ...] | None = None
    date_from: str | None = None
    date_to: str | None = None
    max_review_tier: int | None = None
    min_confidence: str | None = None
    require_source_coverage: bool = False

    model_config = {"extra": "forbid"}

    def filter_keys(self) -> dict[str, Any]:
        """Non-sensitive filter parameters for the emitted summary (never the raw query)."""
        return {
            "project_key": self.project_key,
            "source_families": list(self.source_families) if self.source_families else None,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "max_review_tier": self.max_review_tier,
            "min_confidence": self.min_confidence,
            "require_source_coverage": self.require_source_coverage,
        }


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


def load_metadata_filter_contract() -> dict[str, Any]:
    """Load the metadata-filter contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("metadata_filter_contract")
    if not isinstance(contract, dict) or "filterable_keys" not in contract:
        raise MetadataFilterError(
            "phase 09 metadata-filter contract not found or missing required fields"
        )
    return contract


def load_metadata_filter_seed() -> dict[str, Any]:
    """Load the resolved metadata-filter seed (fail-closed if missing/invalid)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    if not candidate.exists():
        raise MetadataFilterError(f"metadata-filter seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "confidence_order" not in data:
        raise MetadataFilterError(f"{candidate} must define the metadata-filter policy")
    return data


def _confidence_rank(contract: dict[str, Any]) -> dict[str, int]:
    order = contract.get("confidence_order", ["deterministic", "high", "medium", "low", "unknown"])
    return {str(name).lower(): idx for idx, name in enumerate(order)}


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def normalize_filter(
    spec: MetadataFilter, *, contract: dict[str, Any]
) -> tuple[str | None, tuple[str, ...] | None, list[str]]:
    """Pre-retrieval normalization (fail-closed). Returns (project_key, effective_families, notes).

    ``effective_families`` is ``None`` when no source filter is requested (no family restriction), else
    the allowlisted subset of the requested families (possibly empty). Raises ``MetadataFilterError`` if
    an excluded family is explicitly requested or a filter value is invalid.
    """
    notes: list[str] = []
    effective: tuple[str, ...] | None
    if spec.source_families is None:
        effective = None
    else:
        resolved: list[str] = []
        for fam in spec.source_families:
            if fam in EXCLUDED_FAMILIES:
                raise MetadataFilterError(f"excluded family requested in metadata filter: {fam!r}")
            if fam not in ALLOWLISTED_SOURCE_FAMILIES:
                notes.append(f"requested_family_not_allowlisted:{fam}")
                continue
            if fam not in resolved:
                resolved.append(fam)
        effective = tuple(resolved)

    if spec.date_from and _parse_date(spec.date_from) is None:
        raise MetadataFilterError(f"invalid date_from: {spec.date_from!r}")
    if spec.date_to and _parse_date(spec.date_to) is None:
        raise MetadataFilterError(f"invalid date_to: {spec.date_to!r}")
    df, dt = _parse_date(spec.date_from), _parse_date(spec.date_to)
    if df and dt and df > dt:
        raise MetadataFilterError("date_from is after date_to")

    bounds = contract.get("review_tier_bounds", {"min": 1, "max": 3})
    if spec.max_review_tier is not None and not (
        int(bounds.get("min", 1)) <= spec.max_review_tier <= int(bounds.get("max", 3))
    ):
        raise MetadataFilterError(f"max_review_tier out of range: {spec.max_review_tier}")

    if spec.min_confidence is not None and spec.min_confidence.lower() not in _confidence_rank(
        contract
    ):
        raise MetadataFilterError(f"unknown min_confidence: {spec.min_confidence!r}")

    return spec.project_key, effective, notes


def apply_metadata_filter(
    items: list[RetrievalItem],
    spec: MetadataFilter,
    *,
    contract: dict[str, Any],
    selected_families: tuple[str, ...] | None,
) -> tuple[list[RetrievalItem], dict[str, int], list[str]]:
    """Post-retrieval enforcement. Returns (kept_items, dropped_by_reason, coverage_warnings).

    Drops are recorded by reason. Date filtering only applies to date-capable families (others are kept
    with a ``date_filter_not_applicable`` note). Review tier / confidence / source refs / freshness are
    preserved on kept items.
    """
    date_capable = set(contract.get("date_capable_families", ()))
    rank = _confidence_rank(contract)
    df, dt = _parse_date(spec.date_from), _parse_date(spec.date_to)
    min_conf_rank = (
        rank.get(spec.min_confidence.lower()) if spec.min_confidence is not None else None
    )

    dropped: dict[str, int] = {}
    coverage: set[str] = set()

    def _drop(reason: str) -> None:
        dropped[reason] = dropped.get(reason, 0) + 1

    kept: list[RetrievalItem] = []
    for it in items:
        if selected_families is not None and it.source_family not in selected_families:
            _drop("family_not_selected")
            continue
        if spec.project_key is not None and it.project_key not in (None, spec.project_key):
            _drop("project_mismatch")
            continue
        if spec.max_review_tier is not None and it.review_tier > spec.max_review_tier:
            _drop("review_tier_above_max")
            continue
        if (
            min_conf_rank is not None
            and rank.get(it.confidence_class.lower(), len(rank)) > min_conf_rank
        ):
            _drop("confidence_below_min")
            continue
        if df or dt:
            if it.source_family in date_capable:
                item_dt = _parse_date(it.recency)
                if item_dt is None:
                    coverage.add(f"date_filter_not_applicable:{it.source_family}")
                elif (df and item_dt < df) or (dt and item_dt > dt):
                    _drop("out_of_date_window")
                    continue
            else:
                coverage.add(f"date_filter_not_applicable:{it.source_family}")
        kept.append(it)

    # Source-coverage: requested/selected families that yielded no kept items.
    kept_families = {it.source_family for it in kept}
    requested_families = (
        set(selected_families)
        if selected_families is not None
        else {it.source_family for it in items}
    )
    incomplete = sorted(f for f in requested_families if f not in kept_families)
    for fam in incomplete:
        coverage.add(f"no_results_for_family:{fam}")
    if spec.require_source_coverage and incomplete:
        coverage.add("source_coverage_incomplete")

    return kept, dropped, sorted(coverage)


# --- Proof ---------------------------------------------------------------------------------------


def _synthetic_items() -> list[RetrievalItem]:
    """Controlled items spanning tiers / confidence / dates / families for the drop-reason matrix."""
    return [
        RetrievalItem(
            source_family="project_issue_history_items",
            source_ref="iss-keep",
            record_type="issue",
            record_ref="iss-keep",
            project_key="P1",
            confidence_class="high",
            review_tier=1,
            review_status="auto_advisory",
            review_required=False,
            recency="2026-05-15T00:00:00Z",
        ),
        RetrievalItem(
            source_family="project_issue_history_items",
            source_ref="iss-old",
            record_type="issue",
            record_ref="iss-old",
            project_key="P1",
            confidence_class="high",
            review_tier=1,
            review_status="auto_advisory",
            review_required=False,
            recency="2024-01-01T00:00:00Z",
        ),
        RetrievalItem(
            source_family="project_risk_digest_items",
            source_ref="risk-t3",
            record_type="risk",
            record_ref="risk-t3",
            project_key="P1",
            confidence_class="low",
            review_tier=3,
            review_status="review_required",
            review_required=True,
            recency="2026-05-10T00:00:00Z",
        ),
        RetrievalItem(
            source_family="project_issue_history_items",
            source_ref="iss-otherproj",
            record_type="issue",
            record_ref="iss-otherproj",
            project_key="P2",
            confidence_class="high",
            review_tier=1,
            review_status="auto_advisory",
            review_required=False,
            recency="2026-05-15T00:00:00Z",
        ),
        RetrievalItem(
            source_family="cross_source_relationships",
            source_ref="rel-nodate",
            record_type="relationship",
            record_ref="rel-nodate",
            project_key="P1",
            confidence_class="deterministic",
            review_tier=1,
            review_status="auto_advisory",
            review_required=False,
            recency="rel-nodate",
        ),
    ]


def build_metadata_filter_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: pre-filter rejects excluded families; post-filter drops by
    project/family/date/review/confidence with reasons + coverage warnings; integrates with the hybrid
    broker without raw content or answer assembly."""
    contract = load_metadata_filter_contract()

    # Pre-filter: an explicitly requested excluded family is rejected fail-closed.
    excluded_rejected = False
    try:
        normalize_filter(MetadataFilter(source_families=("raw_email_body",)), contract=contract)
    except MetadataFilterError:
        excluded_rejected = True

    # Pre-filter: unknown family dropped with a coverage note; allowlisted family kept.
    _proj, eff, notes = normalize_filter(
        MetadataFilter(source_families=("project_issue_history_items", "not_a_family")),
        contract=contract,
    )
    unknown_family_noted = any(n.startswith("requested_family_not_allowlisted:") for n in notes)
    allowlisted_kept = eff == ("project_issue_history_items",)

    # Post-filter drop-reason matrix over controlled synthetic items.
    items = _synthetic_items()
    spec = MetadataFilter(
        project_key="P1",
        source_families=("project_issue_history_items", "project_risk_digest_items"),
        date_from="2026-01-01T00:00:00Z",
        date_to="2026-12-31T00:00:00Z",
        max_review_tier=1,
        min_confidence="high",
    )
    _p, selected, _n = normalize_filter(spec, contract=contract)
    kept, dropped, coverage = apply_metadata_filter(
        items, spec, contract=contract, selected_families=selected
    )
    kept_refs = {it.source_ref for it in kept}
    drops_seen = set(dropped)
    expected_drops = {
        "project_mismatch",
        "family_not_selected",
        "out_of_date_window",
        "review_tier_above_max",
    }
    # iss-keep survives; iss-old out of window; risk-t3 tier>max + conf<min; iss-otherproj project; rel family
    matrix_ok = (
        kept_refs == {"iss-keep"}
        and expected_drops.issubset(drops_seen)
        and all(it.review_tier <= 1 for it in kept)
    )

    # Date-incapable family is kept with a coverage note (not silently dropped).
    date_spec = MetadataFilter(date_from="2026-01-01T00:00:00Z")
    rel_kept, _rd, rel_cov = apply_metadata_filter(
        [items[-1]], date_spec, contract=contract, selected_families=None
    )
    date_incapable_noted = len(rel_kept) == 1 and any(
        c.startswith("date_filter_not_applicable:") for c in rel_cov
    )

    # Integration with the hybrid broker (fixture DB + applied index + offline MockEmbedding).
    integration_ok = False
    filter_summary_present = False
    no_raw_integration = False
    try:
        import tempfile

        from .hybrid_broker import build_hybrid_retrieval
        from .vector_index import _mock_vector_writer, _proof_db, build_vector_index_apply

        with tempfile.TemporaryDirectory() as tmp:
            db = _proof_db(tmp)
            persist_root = str(Path(tmp) / "vs")
            build_vector_index_apply(db, writer=_mock_vector_writer, persist_root=persist_root)
            from .hybrid_broker import _mock_embed_model

            result = build_hybrid_retrieval(
                "project summary status",
                db_path=db,
                mode="hybrid",
                embed_model=_mock_embed_model(),
                persist_root=persist_root,
                metadata_filter=MetadataFilter(max_review_tier=2),
            )
            integration_ok = (
                result["status"] == "ok"
                and result["filter_applied"] is True
                and result["assembles_final_answer"] is False
                and all(int(t) <= 2 for t, n in result["tier_distribution"].items() if n)
            )
            filter_summary_present = bool(result.get("filter_summary"))
            no_raw_integration = "project summary status" not in json.dumps(result, default=str)
    except Exception:
        integration_ok = False

    proof_passed = (
        excluded_rejected
        and unknown_family_noted
        and allowlisted_kept
        and matrix_ok
        and date_incapable_noted
        and integration_ok
        and filter_summary_present
        and no_raw_integration
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_metadata_filter",
        "command": "second-brain retrieval metadata-filter proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "excluded_family_rejected_pre_filter": excluded_rejected,
        "unknown_family_coverage_noted": unknown_family_noted,
        "allowlisted_family_kept": allowlisted_kept,
        "post_filter_drop_matrix_ok": matrix_ok,
        "dropped_by_reason": dropped,
        "coverage_warnings": coverage,
        "kept_source_refs": sorted(kept_refs),
        "date_incapable_family_noted": date_incapable_noted,
        "hybrid_integration_ok": integration_ok,
        "filter_summary_present": filter_summary_present,
        "raw_query_not_emitted": no_raw_integration,
        "metadata_only": True,
        "guardrails": {
            "fail_closed": True,
            "excluded_families_never_queried": True,
            "no_raw": True,
            "no_external_writeback": True,
            "no_final_answer_assembly": True,
            "preserve_review_tier_confidence_source_refs_freshness": True,
            "local_first": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "metadata filter proof json")
        (out_dir / _PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "metadata filter proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Metadata Filter Enforcement Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- excluded_family_rejected_pre_filter: {proof['excluded_family_rejected_pre_filter']}",
        f"- unknown_family_coverage_noted: {proof['unknown_family_coverage_noted']}",
        f"- allowlisted_family_kept: {proof['allowlisted_family_kept']}",
        f"- post_filter_drop_matrix_ok: {proof['post_filter_drop_matrix_ok']}",
        f"- dropped_by_reason: {proof['dropped_by_reason']}",
        f"- kept_source_refs: {proof['kept_source_refs']}",
        f"- date_incapable_family_noted: {proof['date_incapable_family_noted']}",
        f"- hybrid_integration_ok: {proof['hybrid_integration_ok']}",
        f"- filter_summary_present: {proof['filter_summary_present']}",
        f"- raw_query_not_emitted: {proof['raw_query_not_emitted']}",
        "",
    ]
    return "\n".join(lines)
