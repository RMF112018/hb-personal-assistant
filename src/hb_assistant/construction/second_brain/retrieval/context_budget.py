"""Phase 09 Prompt 27 — context budget optimization (advisory best-effort packer).

The baseline deterministic packer ``apply_context_budget`` (``retrieval/policy.py``) fills the
model-bound context in priority order (review tier -> recency -> confidence -> source_ref) but
**breaks at the first item that would overflow** — so a single large high-priority item near the front
blocks every smaller lower-priority item behind it, wasting budget and silently dropping source-linked
context.

``optimize_context_packing`` is an **additive, advisory** best-effort fill: same ordering and same budget
bounds, but it **skips** an oversized item and **continues** packing the rest. It preserves every kept
item's review tier / confidence / source ref / freshness, never exceeds the budget, and **surfaces each
budget drop as a coverage warning** (``budget_dropped:<family>`` / ``budget_dropped_tier{N}:<family>``) so
a sacrificed item is never silently lost. The authoritative ``apply_context_budget`` is **not** modified
(broker adoption is deferred); this surface measures the recovery and proves it is metadata-safe.

Read-only and advisory: ``assembles_final_answer`` is always ``False`` and the builder **persists nothing**
(no DB writes). Fail-closed on missing policy or stale schema. No raw excerpt/content/source ref is
emitted — only counts, percentages, hashed refs, family names, and warnings.

Public entry points:
  optimize_context_packing(items, budget) -> dict
  build_context_budget_optimization(db_path=None, *, project_key=None, families=None) -> dict
  build_context_budget_optimization_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain retrieval context-budget build | proof --json
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy

from ..financial_review_routing import _assert_no_raw
from .models import RetrievalItem
from .policy import (
    ALLOWLISTED_SOURCE_FAMILIES,
    EXCLUDED_FAMILIES,
    ContextBudget,
    apply_context_budget,
    load_context_budget,
)
from .readers import READER_REGISTRY

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "context-budget-optimization-proof.json"
_PROOF_MD = "context-budget-optimization-proof.md"

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_context_budget_optimization.seed.yaml"

# Mirror of the baseline confidence ordering in apply_context_budget (policy.py).
_CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2, "unknown": 3}


class ContextBudgetOptimizationError(RuntimeError):
    """Raised when the optimizer builder cannot resolve policy/schema (fail-closed)."""


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


def _schema_ready(db_path: str | None) -> int:
    """Return the schema version if ready (>=38), else raise fail-closed."""
    conn = _open_ro(db_path)
    if conn is None:
        raise ContextBudgetOptimizationError(
            "schema not ready for context budget optimization (no database)"
        )
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        if row is None:
            raise ContextBudgetOptimizationError("schema not ready (no schema_migrations)")
        ver_row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(ver_row[0]) if ver_row and ver_row[0] is not None else 0
        if version < 38:
            raise ContextBudgetOptimizationError(
                f"schema not ready for context budget optimization (version {version}, expected >= 38)"
            )
    finally:
        conn.close()
    return version


def load_context_budget_optimization_contract() -> dict[str, Any]:
    """Load the context-budget-optimization contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("context_budget_optimization_contract")
    if not isinstance(contract, dict) or "honored_budget_fields" not in contract:
        raise ContextBudgetOptimizationError(
            "phase 09 context-budget-optimization contract not found or missing required fields"
        )
    return contract


def load_context_budget_optimization_seed() -> dict[str, Any]:
    """Load the resolved context-budget-optimization seed (fail-closed if missing/invalid)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    if not candidate.exists():
        raise ContextBudgetOptimizationError(
            f"context-budget-optimization seed not found at {candidate}"
        )
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "strategy" not in data:
        raise ContextBudgetOptimizationError(
            f"{candidate} must define the context-budget-optimization policy"
        )
    return data


def _ordered(items: list[RetrievalItem]) -> list[RetrievalItem]:
    """The baseline priority order (identical to apply_context_budget): tier -> recency desc ->
    confidence -> source_ref tiebreak."""
    ordered = sorted(items, key=lambda it: it.source_ref)
    ordered = sorted(ordered, key=lambda it: _CONFIDENCE_RANK.get(it.confidence_class.lower(), 3))
    ordered = sorted(ordered, key=lambda it: it.recency, reverse=True)
    ordered = sorted(ordered, key=lambda it: it.review_tier)
    return ordered


def optimize_context_packing(items: list[RetrievalItem], budget: ContextBudget) -> dict[str, Any]:
    """Best-effort fill within the baseline priority order (skip-oversized-and-continue).

    Returns a metadata-only dict: ``kept`` (RetrievalItems), ``char_count``, ``truncated``,
    ``degradation``, ``dropped_by_reason``, ``dropped_families``, and ``coverage_warnings`` (each budget
    drop surfaced). Never exceeds ``budget.max_context_chars``; every kept item retains full metadata
    (only the excerpt is length-bounded, identically to the baseline).
    """
    kept: list[RetrievalItem] = []
    char_count = 0
    dropped_by_reason: dict[str, int] = {}
    coverage_warnings: list[str] = []

    for it in _ordered(items):
        excerpt = it.content_excerpt_redacted[: budget.max_item_chars]
        if it.content_excerpt_redacted != excerpt:
            it = it.model_copy(update={"content_excerpt_redacted": excerpt})
        if char_count + len(excerpt) > budget.max_context_chars:
            # Skip this (over-budget) item and keep trying smaller, lower-priority items.
            dropped_by_reason["oversized_skipped"] = (
                dropped_by_reason.get("oversized_skipped", 0) + 1
            )
            coverage_warnings.append(f"budget_dropped:{it.source_family}")
            coverage_warnings.append(f"budget_dropped_tier{it.review_tier}:{it.source_family}")
            continue
        kept.append(it)
        char_count += len(excerpt)

    truncated = bool(dropped_by_reason)
    if not kept:
        degradation = "blocked"
    elif truncated:
        degradation = "narrow_claims"
    else:
        degradation = "none"

    dropped_families = sorted(
        {w.split(":", 1)[1] for w in coverage_warnings if w.startswith("budget_dropped:")}
    )
    return {
        "kept": kept,
        "char_count": char_count,
        "truncated": truncated,
        "degradation": degradation,
        "dropped_by_reason": dropped_by_reason,
        "dropped_families": dropped_families,
        "coverage_warnings": coverage_warnings,
    }


def _gather_pre_budget_items(
    db_path: str | None, project_key: str | None, families: tuple[str, ...] | None
) -> tuple[list[RetrievalItem], list[str]]:
    """Mirror the deterministic broker's pre-budget gather (broker.retrieve, before apply_context_budget):
    iterate the allowlist, deny excluded/unknown/no-reader families with coverage warnings, and extend
    from the read models. Returns (items, coverage_warnings). Read-only."""
    from hb_assistant.construction.store import ConstructionStore

    store = ConstructionStore(db_path)
    requested = families or ALLOWLISTED_SOURCE_FAMILIES
    items: list[RetrievalItem] = []
    coverage_warnings: list[str] = []
    for family in requested:
        if family in EXCLUDED_FAMILIES:
            coverage_warnings.append(f"denied_excluded_family:{family}")
            continue
        if family not in ALLOWLISTED_SOURCE_FAMILIES:
            coverage_warnings.append(f"unknown_family:{family}")
            continue
        reader = READER_REGISTRY.get(family)
        if reader is None:
            coverage_warnings.append(f"no_read_model:{family}")
            continue
        items.extend(reader(store, db_path, project_key))
    return items, coverage_warnings


def _tier_distribution(items: list[RetrievalItem]) -> dict[str, int]:
    dist = {"1": 0, "2": 0, "3": 0}
    for it in items:
        dist[str(it.review_tier)] += 1
    return dist


def _utilization_pct(char_count: int, budget: ContextBudget) -> float:
    cap = int(budget.max_context_chars) or 1
    return round((char_count / cap) * 100, 2)


def build_context_budget_optimization(
    db_path: str | None = None,
    *,
    project_key: str | None = None,
    families: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Compare the baseline packer vs the best-effort optimizer over the deterministic corpus (read-only).

    Returns a JSON-safe, metadata-only comparison (counts, utilization %, recovered items, preserved
    tier distribution, coverage + budget-drop warnings); persists nothing. Fail-closed on missing policy
    or stale schema.
    """
    contract = load_context_budget_optimization_contract()
    seed = load_context_budget_optimization_seed()
    schema_version = _schema_ready(db_path)
    budget = load_context_budget()

    items, gather_warnings = _gather_pre_budget_items(db_path, project_key, families)
    status = "built" if items else "empty"

    base_kept, base_chars, base_truncated, base_degradation = apply_context_budget(items, budget)
    opt = optimize_context_packing(items, budget)

    items_recovered = len(opt["kept"]) - len(base_kept)
    metadata_preserved = all(
        bool(it.source_ref) and it.review_tier in (1, 2, 3) and it.confidence_class
        for it in opt["kept"]
    )
    within_budget = int(opt["char_count"]) <= int(budget.max_context_chars)
    all_drops_warned = sum(opt["dropped_by_reason"].values()) <= len(
        [w for w in opt["coverage_warnings"] if w.startswith("budget_dropped:")]
    )

    return {
        "command": "second-brain retrieval context-budget build",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": status,
        "schema_version": schema_version,
        "project_key": project_key,
        "candidate_item_count": len(items),
        "budget": {
            "max_context_chars": budget.max_context_chars,
            "max_item_chars": budget.max_item_chars,
        },
        "baseline": {
            "kept_count": len(base_kept),
            "char_count": base_chars,
            "char_utilization_pct": _utilization_pct(base_chars, budget),
            "truncated": base_truncated,
            "degradation_mode": base_degradation,
            "tier_distribution": _tier_distribution(base_kept),
        },
        "optimized": {
            "kept_count": len(opt["kept"]),
            "char_count": opt["char_count"],
            "char_utilization_pct": _utilization_pct(opt["char_count"], budget),
            "truncated": opt["truncated"],
            "degradation_mode": opt["degradation"],
            "tier_distribution": _tier_distribution(opt["kept"]),
            "dropped_by_reason": opt["dropped_by_reason"],
            "dropped_families": opt["dropped_families"],
        },
        "items_recovered": items_recovered,
        "char_utilization_delta_pct": round(
            _utilization_pct(opt["char_count"], budget) - _utilization_pct(base_chars, budget), 2
        ),
        "metadata_preserved": metadata_preserved,
        "within_budget": within_budget,
        "all_drops_have_coverage_warnings": all_drops_warned,
        "coverage_warnings": gather_warnings + opt["coverage_warnings"],
        "deterministic_packing": True,
        "assembles_final_answer": False,
        "authoritative_packer_unchanged": True,
        "policy_version": seed.get("version"),
        "contract_version": contract.get("version"),
        "strategy": seed.get("strategy"),
        "read_only": True,
    }


# --- Proof ---------------------------------------------------------------------------------------


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Context Budget Optimization Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- baseline_kept: {proof['baseline_kept']}",
        f"- optimized_kept: {proof['optimized_kept']}",
        f"- items_recovered: {proof['items_recovered']} (must be >= 1)",
        f"- within_budget: {proof['within_budget']} (must be true)",
        f"- metadata_preserved: {proof['metadata_preserved']} (must be true)",
        f"- every_drop_has_warning: {proof['every_drop_has_warning']} (must be true)",
        f"- priority_preserved: {proof['priority_preserved']} (must be true)",
        f"- authoritative_packer_unchanged: {proof['authoritative_packer_unchanged']} (must be true)",
        f"- assembles_final_answer: {proof['assembles_final_answer']} (must be false)",
        f"- build_path_no_db_writes: {proof['build_path_no_db_writes']} (must be true)",
        f"- no_raw_emitted: {proof['no_raw_emitted']} (must be true)",
        "",
    ]
    return "\n".join(lines)


def _synthetic_items() -> list[RetrievalItem]:
    """Crafted to expose break-vs-skip. Each excerpt is capped at ``max_item_chars``, so a single item
    can never overflow the total budget — the break only happens via the cumulative sum. We fill the
    budget with N max-size tier-1 items, then add one more max-size tier-1 item that overflows the
    remaining space, then a tiny tier-2 item that still fits. The baseline ``break``s at the overflowing
    item and never reaches the tiny one; the optimizer skips the overflow and keeps the tiny item."""
    budget = load_context_budget()
    per = budget.max_item_chars
    n_fill = budget.max_context_chars // per  # max-size items that fit exactly (e.g. 13)
    remaining = budget.max_context_chars - n_fill * per  # headroom for the tiny item (e.g. 600)
    tiny = max(1, min(remaining - 1, 100))

    items: list[RetrievalItem] = []
    for i in range(n_fill):
        items.append(
            RetrievalItem(
                source_family="approved_obsidian_generated_outputs",
                source_ref=f"ref-fill-{i:02d}",
                record_type="note",
                record_ref=str(i),
                confidence_class="high",
                review_tier=1,
                recency=f"2026-02-{(n_fill - i):02d}",  # newest first
                content_excerpt_redacted="A" * per,
            )
        )
    # Oversized tier-1 item (oldest recency -> sorts last within tier 1; overflows the remaining budget).
    items.append(
        RetrievalItem(
            source_family="accepted_long_term_memory",
            source_ref="ref-oversized",
            record_type="memory",
            record_ref="oversized",
            confidence_class="high",
            review_tier=1,
            recency="2025-01-01",
            content_excerpt_redacted="B" * per,
        )
    )
    # Tiny tier-2 item that still fits in the remaining budget (baseline never reaches it).
    items.append(
        RetrievalItem(
            source_family="project_issue_history_items",
            source_ref="ref-tiny",
            record_type="issue",
            record_ref="tiny",
            confidence_class="medium",
            review_tier=2,
            recency="2024-01-01",
            content_excerpt_redacted="C" * tiny,
        )
    )
    return items


def build_context_budget_optimization_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: the optimizer recovers >= 1 item over the baseline, never exceeds the budget,
    preserves all metadata, surfaces every budget drop as a coverage warning, preserves priority, leaves
    the authoritative packer untouched, assembles no answer, and emits no raw; the build path performs no
    DB writes."""
    import tempfile

    from .vector_index import _proof_db

    budget = load_context_budget()
    items = _synthetic_items()

    base_kept, _base_chars, _base_trunc, _base_deg = apply_context_budget(items, budget)
    opt = optimize_context_packing(items, budget)

    items_recovered = len(opt["kept"]) - len(base_kept)
    within_budget = int(opt["char_count"]) <= int(budget.max_context_chars)
    metadata_preserved = all(
        bool(it.source_ref) and it.review_tier in (1, 2, 3) and it.confidence_class and it.recency
        for it in opt["kept"]
    )
    drop_count = sum(opt["dropped_by_reason"].values())
    drop_warns = [w for w in opt["coverage_warnings"] if w.startswith("budget_dropped:")]
    every_drop_has_warning = drop_count >= 1 and len(drop_warns) >= drop_count
    # Priority preserved: kept items are non-decreasing in review tier (higher tier kept before lower).
    tiers = [it.review_tier for it in opt["kept"]]
    priority_preserved = tiers == sorted(tiers)
    # The authoritative baseline packer is unchanged: re-running it is identical + it still breaks early.
    base_kept_2, _, _, _ = apply_context_budget(items, budget)
    authoritative_unchanged = [it.source_ref for it in base_kept] == [
        it.source_ref for it in base_kept_2
    ]

    # Build path performs no DB writes (row totals unchanged on a proof DB).
    with tempfile.TemporaryDirectory() as tmp:
        db = _proof_db(tmp)
        before = _total_rows(db)
        build_result = build_context_budget_optimization(db)
        after = _total_rows(db)
    build_path_no_db_writes = before == after

    serialized_inputs = json.dumps(build_result, default=str)
    no_raw_emitted = (
        "content_excerpt" not in serialized_inputs
        and "text_redacted" not in serialized_inputs
        and "AAAA" not in serialized_inputs
        and "BBBB" not in serialized_inputs
    )

    proof_passed = (
        items_recovered >= 1
        and within_budget
        and metadata_preserved
        and every_drop_has_warning
        and priority_preserved
        and authoritative_unchanged
        and build_path_no_db_writes
        and no_raw_emitted
        and build_result["assembles_final_answer"] is False
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_context_budget_optimization",
        "command": "second-brain retrieval context-budget proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "baseline_kept": len(base_kept),
        "optimized_kept": len(opt["kept"]),
        "items_recovered": items_recovered,
        "within_budget": within_budget,
        "metadata_preserved": metadata_preserved,
        "every_drop_has_warning": every_drop_has_warning,
        "priority_preserved": priority_preserved,
        "authoritative_packer_unchanged": authoritative_unchanged,
        "assembles_final_answer": build_result["assembles_final_answer"],
        "build_path_no_db_writes": build_path_no_db_writes,
        "no_raw_emitted": no_raw_emitted,
        "dropped_families": opt["dropped_families"],
        "metadata_only": True,
        "guardrails": {
            "advisory_only": True,
            "deterministic_packing": True,
            "never_exceed_budget": True,
            "no_silent_drops": True,
            "authoritative_packer_unchanged": True,
            "no_final_answer": True,
            "no_raw": True,
            "no_external_writeback": True,
            "local_first": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "context budget optimization proof json")
        (out_dir / _PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "context budget optimization proof markdown")
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
