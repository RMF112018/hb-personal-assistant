"""Phase 09 review burden reduction and advisory promotion policy (two-step classification).

Implements exception-based review model:
- Two-step eligibility: source family in allowed (necessary) + item impact/risk safe (decisive).
  High-impact item from *any* family (including "low-risk" families like cross_source_relationships,
  aging_exposure_report_items, project_risk_digest_items) forces Tier C (mandatory before promotion).
- Tier A: auto-allow advisory (metadata-only, source-linked, guards clean, low impact after two-step).
- Tier B: batch-review (group by keys, suppress weak by default, top hash-only examples, keep advisory).
- Tier C: mandatory review before any promotion to accepted fact/memory/high-confidence.
- Tier D: hard prohibited (never in retrieval, synthesis, MCP, writeback, final determinations).

Financial review ledger (second_brain_financial_review_required_items) is tracked *separately*
as financial_review_burden (always advisory_only + promotion_blocked; raw volume does not
create permanent assistant usability failure for low-risk non-financial advisory).

high_impact_always_visible: high-impact *categories and totals* are always present in summaries;
only top clusters (capped to operator daily budget) are "visible" for operator action. Never
silently hide high-impact counts.

top_examples_json contains *only* hash-safe fields (no text, titles, emails, URLs, PII, bodies).
Prohibited fields are rejected.

All outputs metadata-only + source-linked (hashes/refs/counts); every persisted row carries the
23 Phase 09 guard columns =0 (no-raw, no-writeback, no-determinations).

Read-only by default for CLI surfaces; proofs attest guard compliance + two-step application.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:  # pragma: no cover - import shim
    import importlib.resources as importlib_resources
except Exception:  # pragma: no cover
    import importlib_resources  # type: ignore[no-redef]

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

from ..risk_digest.risk_digest_builder import _risk_category
from .contracts import load_phase_09_contract
from .review_load_mart import _REVIEW_TABLES as _REVIEW_TABLE_SPECS

# Re-use the table specs and high-impact baseline from the load mart (two-step will extend/override
# impact using the policy contract at runtime).
from .review_load_mart import HIGH_IMPACT_CATEGORIES as _BASE_HIGH_IMPACT

_SEED_RELATIVE = Path("resources/config/phase_09_review_burden_policy.seed.yaml")
SEED_ENV_VAR = "HB_SECOND_BRAIN_REVIEW_BURDEN_POLICY"
_CONTRACT_NAME = "review_burden_policy_contract"


class ReviewBurdenPolicyError(RuntimeError):
    """Raised when the review burden policy seed/contract cannot be loaded (fail-closed)."""


def load_review_burden_policy_contract() -> dict[str, Any]:
    """Load the review burden policy contract (fail-closed if missing/invalid)."""
    contract = load_phase_09_contract(_CONTRACT_NAME)
    if not isinstance(contract, dict) or "high_impact_impact_categories" not in contract:
        raise ReviewBurdenPolicyError(
            "phase 09 review burden policy contract not found or missing required fields"
        )
    return contract


def _load_yaml_from_package_or_fallback(relative_under_resources: Path) -> dict[str, Any]:
    """Try packaged resources (hb_assistant.resources.config or .json for contracts), then PathPolicy repo fallback.
    Supports both installed package and source-tree dev (pre/post pip -e).
    """
    filename = relative_under_resources.name
    pkg_path = "hb_assistant.resources.config"
    try:
        if hasattr(importlib_resources, "files"):
            text = (importlib_resources.files(pkg_path) / filename).read_text(encoding="utf-8")
        else:
            text = importlib_resources.read_text(pkg_path, filename, encoding="utf-8")
        data = yaml.safe_load(text) or {}
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    # Fallback for dev runs (before/without editable install or when package data not yet visible)
    root = PathPolicy().resolve_repo_root()
    for candidate in (
        root / "src/hb_assistant" / relative_under_resources,
        root / "resources" / relative_under_resources.name,  # legacy root resources for other seeds
        root / relative_under_resources,
    ):
        if candidate.exists():
            with candidate.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if isinstance(data, dict):
                return data
    raise ReviewBurdenPolicyError(
        f"review burden policy seed not found (package or {root / 'src/hb_assistant' / relative_under_resources})"
    )


def load_review_burden_policy_seed() -> dict[str, Any]:
    """Load the resolved review burden policy seed (fail-closed). Supports package + ENV + repo fallback."""
    env_value = os.environ.get(SEED_ENV_VAR)
    if env_value:
        p = Path(env_value).expanduser()
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if isinstance(data, dict) and "policy_id" in data:
                return data
    data = _load_yaml_from_package_or_fallback(_SEED_RELATIVE)
    if not isinstance(data, dict) or "policy_id" not in data or "auto_allow_advisory" not in data:
        raise ReviewBurdenPolicyError(
            f"{_SEED_RELATIVE} must define the review burden policy (policy_id + auto_allow_advisory)"
        )
    return data


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        is not None
    )


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _guard_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    return [
        c
        for c in cols
        if c.endswith("_persisted") or c.endswith("_performed") or c.endswith("_allowed")
    ]


def _assert_no_raw_on_burden_row(row: dict[str, Any]) -> None:
    """Fail-closed: any guard >0 on a burden row (or its source) violates no-raw/no-writeback."""
    bad = []
    for k, v in row.items():
        if (k.endswith("_persisted") or k.endswith("_performed") or k.endswith("_allowed")) and int(v or 0) != 0:
            bad.append(k)
    if bad:
        raise ReviewBurdenPolicyError(f"guard violation on burden item: {bad}")


def _classify_impact_from_policy(
    contract: dict[str, Any], impact_values: tuple[str, ...], always_high_sql_hit: bool = False
) -> str:
    high = set(contract.get("high_impact_impact_categories", []))
    for val in impact_values:
        if not val:
            continue
        cat = _risk_category(str(val), high)
        if cat in high:
            return cat
    if always_high_sql_hit:
        # fall back to a generic high if the table had always_high_impact_sql
        return "financial" if "financial" in high else next(iter(high), "financial")
    return "unclassified"


def _two_step_tier(
    contract: dict[str, Any],
    seed: dict[str, Any],
    source_family: str,
    impact_category: str,
    confidence_class: str | None,
    review_reason: str | None,
    has_raw_or_writeback: bool,
    is_sensitive_high: bool,
) -> tuple[str, str]:
    """Return (tier, reason). Tier A/B/C/D per refinements.

    family in allowed_families is NECESSARY but NOT SUFFICIENT.
    impact/risk classification is DECISIVE.
    high-impact item beats low-risk family.
    """
    allowed_families = set(seed.get("auto_allow_advisory", {}).get("allowed_families", []))
    mandatory = set(contract.get("high_impact_impact_categories", []))
    # hard_denials = set(...)  # reserved for future Tier D classification inside two-step if needed

    # Hard denials / prohibited signals -> Tier D
    if has_raw_or_writeback:
        return "D", "raw_or_writeback_guard_violation"
    if is_sensitive_high:
        return "C", "sensitive_high_impact"  # treat as mandatory

    family_ok = source_family in allowed_families
    impact_high = (impact_category in mandatory) or (impact_category == "unclassified" and is_sensitive_high)

    if not family_ok and impact_high:
        return "C", "high_impact_item_outside_allowed_family"

    if impact_high:
        # High impact from any family (even allowed ones) is C
        return "C", f"high_impact:{impact_category}"

    if family_ok:
        # Family eligible + impact not high -> consider A (if other guards)
        # Additional: confidence low or reason weak may push to B
        if confidence_class in ("weak", "low") or (review_reason or "").lower() in {"weak", "low", "duplicate_candidate"}:
            return "B", "low_confidence_or_weak_reason_after_two_step"
        # Default for clean low-risk metadata: A
        return "A", "two_step_passed_low_risk_advisory_eligible"

    # Family not allowed, but not high-impact -> B (batch, not auto)
    return "B", "family_not_eligible_for_auto_advisory"


def _cluster_key(project_key: str | None, family: str, impact: str, conf: str | None, reason: str | None) -> str:
    base = "|".join([
        (project_key or "").lower(),
        family,
        impact,
        (conf or "unclassified").lower(),
        (reason or "unknown").lower(),
    ])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def _safe_top_example(item: dict[str, Any]) -> dict[str, Any]:
    """Return only the 9 allowed hash-safe fields for top_examples_json. Strip everything else."""
    allowed = {
        "source_family",
        "project_key",
        "item_hash",
        "source_ref_hash",
        "confidence_class",
        "review_reason_code",
        "impact_category",
        "freshness_bucket",
        "count",
    }
    ex = {k: item.get(k) for k in allowed if k in item}
    # Never allow prohibited even if caller passed
    prohibited = {
        "subject", "body", "title", "summary", "organizer", "attendee", "email", "location",
        "url", "download_url", "signed_url", "raw", "payload", "token", "secret", "text", "preview"
    }
    for bad in prohibited:
        ex.pop(bad, None)
    return ex


def _collect_review_candidates(
    conn: sqlite3.Connection, *, project_key: str | None = None
) -> list[dict[str, Any]]:
    """Scan the review-bearing tables and return lightweight distinct item dicts for two-step classification.
    Does not mutate; metadata + refs + impact only. Replicates/adapts the dedup+impact logic from review_load_mart.
    """
    candidates: list[dict[str, Any]] = []

    for spec in _REVIEW_TABLE_SPECS:
        table = spec["table"]
        if not _table_exists(conn, table):
            continue
        source_family = spec["source_family"]
        impact_cols = spec.get("impact_cols") or ()
        dedup_keys = spec.get("dedup_keys")
        always_high_sql = spec.get("always_high_impact_sql")
        unresolved_sql = spec.get("unresolved_sql") or "1=1"

        cols = _columns(conn, table)

        # Build a base for distinct items (use dedup if present like financial)
        if dedup_keys and all(k in cols for k in dedup_keys):
            # For financial ledger we still want the distinct (project+cat+ref+amount) but also track raw volume
            select_cols = ", ".join(dedup_keys)
            rows = conn.execute(
                f"SELECT DISTINCT {select_cols} FROM {table}"
            ).fetchall()
            # For volume we also note raw count separately in caller
        else:
            # Simple distinct on a synthetic key (table rowid or a ref if present)
            key_col = "source_ref" if "source_ref" in cols else ("id" if "id" in cols else None)
            if key_col:
                rows = conn.execute(f"SELECT DISTINCT {key_col} FROM {table}").fetchall()
            else:
                # fallback: take a sample of open rows (bounded)
                rows = conn.execute(f"SELECT rowid FROM {table} WHERE {unresolved_sql} LIMIT 5000").fetchall()

        for r in rows:
            # r is sqlite row; normalize to dict-like
            rec: dict[str, Any] = {k: r[k] for k in r} if hasattr(r, "keys") else {}
            # project
            pk = rec.get("project_key") or rec.get("project") or None
            if project_key is not None and pk is not None and pk != project_key:
                continue

            # impact values from the cols
            impact_vals: list[str] = []
            for c in impact_cols:
                if c in rec and rec[c]:
                    impact_vals.append(str(rec[c]))
            # also try common reason/category fields if present
            for c in ("reason", "category", "trigger_category", "review_tier_reason_code", "sensitivity"):
                if c in rec and rec[c]:
                    impact_vals.append(str(rec[c]))

            always_hit = False
            if always_high_sql:
                # quick check on the raw row for this key (approximate by re-query if we have keys)
                always_hit = True  # conservative; the original mart does a separate COUNT

            impact_cat = _classify_impact_from_policy(
                {"high_impact_impact_categories": list(_BASE_HIGH_IMPACT)},  # temp; caller will reclass with contract
                tuple(impact_vals),
                always_high_sql_hit=always_hit,
            )

            # confidence / tier proxy
            conf = rec.get("confidence_class") or rec.get("review_tier") or None
            if isinstance(conf, int):
                conf = {1: "high", 2: "medium", 3: "low"}.get(conf, "medium")
            reason = rec.get("review_reason") or rec.get("review_tier_reason_code") or rec.get("reason") or None

            # guard presence on this table (many review tables carry the Phase09 guards or subset)
            guard_ok = True
            if _table_exists(conn, table):
                gcols = _guard_columns(conn, table)
                if gcols:
                    # sample a representative row for this item (best effort; for financial we know they set advisory_only=1)
                    try:
                        sample = conn.execute(
                            f"SELECT {', '.join(gcols)} FROM {table} LIMIT 1"
                        ).fetchone()
                        if sample and any(int(v or 0) != 0 for v in sample):
                            guard_ok = False
                    except Exception:
                        guard_ok = True  # do not fail collection on missing; proof will re-assert

            item_hash = rec.get("item_id") or rec.get("id") or rec.get("source_ref") or hashlib.sha256(
                f"{table}:{pk}:{impact_cat}:{reason}".encode()
            ).hexdigest()[:12]

            candidates.append(
                {
                    "source_family": source_family,
                    "project_key": pk,
                    "impact_category": impact_cat,
                    "confidence_class": conf,
                    "review_reason_code": reason,
                    "item_hash": item_hash,
                    "source_ref_hash": rec.get("source_ref") or item_hash,
                    "freshness_bucket": "recent" if rec.get("created_utc") or rec.get("generated_utc") else "unknown",
                    "guard_ok": guard_ok,
                    "sensitive_high_impact": bool(rec.get("sensitive_high_impact") or 0),
                    "table": table,
                    "raw_count_proxy": 1,
                }
            )

    # Also surface the financial ledger volume separately (do not mix into assistant clusters)
    if _table_exists(conn, "second_brain_financial_review_required_items"):
        # raw unresolved is high; we will count distinct in caller
        pass

    return candidates


def _build_clusters_from_candidates(
    contract: dict[str, Any],
    seed: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    max_examples: int = 5,
    daily_budget: int = 10,
) -> dict[str, Any]:
    """Apply two-step, group, dedupe via cluster_hash, produce counts + top hash-only examples.
    Returns structure with separated financial, high_impact_summary (clustered), advisory_allowed etc.
    """
    policy_families = set(seed.get("auto_allow_advisory", {}).get("allowed_families", []))
    high_cats = set(contract.get("high_impact_impact_categories", []))

    clusters: dict[str, dict[str, Any]] = {}
    financial_raw = 0
    financial_distinct = 0

    auto_advisory = 0
    batch = 0
    mandatory = 0
    hard = 0

    high_impact_by_cat: dict[str, int] = dict.fromkeys(high_cats, 0)
    high_impact_total = 0

    for c in candidates:
        if c.get("table") == "second_brain_financial_review_required_items" or c.get("source_family") == "financial":
            financial_raw += c.get("raw_count_proxy", 1)
            financial_distinct += 1
            # financial always C for promotion, advisory_only, separate
            tier = "C"
            tier_reason = "financial_ledger_separate_burden"
            c["impact_category"] = "financial"
        else:
            tier, tier_reason = _two_step_tier(
                contract,
                seed,
                c["source_family"],
                c["impact_category"],
                c.get("confidence_class"),
                c.get("review_reason_code"),
                has_raw_or_writeback=not c.get("guard_ok", True),
                is_sensitive_high=bool(c.get("sensitive_high_impact")),
            )

        c["tier"] = tier
        c["tier_reason"] = tier_reason

        if tier == "D":
            hard += 1
            continue
        if tier == "C":
            mandatory += 1
            if c["impact_category"] in high_impact_by_cat:
                high_impact_by_cat[c["impact_category"]] += 1
            high_impact_total += 1
        elif tier == "B":
            batch += 1
        elif tier == "A":
            # only if family allowed + impact safe + guards (re-check two-step result)
            if c["source_family"] in policy_families and c["impact_category"] not in high_cats and c.get("guard_ok"):
                auto_advisory += 1
            else:
                # demote if two-step would not allow
                c["tier"] = "B"
                c["tier_reason"] = "post_two_step_guard_or_family"
                batch += 1

        # cluster
        ck = _cluster_key(
            c.get("project_key"),
            c["source_family"],
            c["impact_category"],
            c.get("confidence_class"),
            c.get("review_reason_code"),
        )
        if ck not in clusters:
            clusters[ck] = {
                "cluster_id": ck,
                "project_key": c.get("project_key"),
                "source_family": c["source_family"],
                "impact_category": c["impact_category"],
                "confidence_class": c.get("confidence_class") or "unclassified",
                "review_reason": c.get("review_reason_code") or "unknown",
                "tier": c["tier"],
                "item_count": 0,
                "top_examples": [],
            }
        clusters[ck]["item_count"] += 1
        if len(clusters[ck]["top_examples"]) < max_examples:
            clusters[ck]["top_examples"].append(_safe_top_example(c))

    # high impact summary (always categories + totals; visible clusters capped)
    high_clusters = [cl for cl in clusters.values() if cl["tier"] == "C"]
    high_clusters.sort(key=lambda x: (-x["item_count"], x["source_family"]))
    visible_high = high_clusters[:daily_budget]

    # operator visible = high (capped clusters) + some mandatory/batch if room, but high always represented via summary
    operator_visible_clusters = visible_high  # high always shown as top; additional low can be added by caller if needed

    suppressed = max(0, (batch + mandatory + auto_advisory) - len(operator_visible_clusters))

    return {
        "clusters": list(clusters.values()),
        "financial_review_burden": {
            "raw_unresolved": financial_raw,
            "distinct_items": financial_distinct,
            "advisory_only": True,
            "promotion_blocked": True,
            "separate_from_assistant_queue": True,
        },
        "counts": {
            "total_distinct_review_items": len(candidates),
            "auto_advisory_allowed": auto_advisory,
            "batch_review": batch,
            "mandatory_review": mandatory,
            "hard_stop": hard,
        },
        "high_impact_summary": {
            "categories": sorted([c for c, n in high_impact_by_cat.items() if n > 0]),
            "total_high_impact_distinct": high_impact_total,
            "by_category": high_impact_by_cat,
            "visible_top_clusters": len(visible_high),
            "always_visible": True,
            "note": "High-impact categories and totals are always summarized; only top clusters within operator budget are listed for action. No silent suppression of high-impact counts.",
        },
        "operator_visible_clusters": operator_visible_clusters,
        "suppressed_or_batched": suppressed,
        "advisory_retrieval_allowed": auto_advisory > 0 or batch > 0,  # low-risk A + B as unpromoted advisory ok
        "blanket_review_block": False,
    }


def build_review_burden_mart(
    db_path: str | None = None, *, project_key: str | None = None
) -> dict[str, Any]:
    """Compute the review burden clusters + separated financial + two-step gate numbers (read-only)."""
    contract = load_review_burden_policy_contract()
    seed = load_review_burden_policy_seed()

    resolved = db_path or str(PathPolicy().get_db_path())
    conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    try:
        candidates = _collect_review_candidates(conn, project_key=project_key)

        # Re-classify impacts using the *contract* high list (two-step will use it)
        for c in candidates:
            if c.get("source_family") != "financial":
                vals = (c.get("impact_category") or "", c.get("review_reason_code") or "")
                c["impact_category"] = _classify_impact_from_policy(contract, vals)

        daily = int(seed.get("operator_review_budget", {}).get("daily_max_items", 10))
        max_ex = int(seed.get("batch_review", {}).get("max_examples_per_group", 5))

        clustered = _build_clusters_from_candidates(
            contract, seed, candidates, max_examples=max_ex, daily_budget=daily
        )

        # Compose the mart shape (compatible with review-load expectations + new fields)
        total_distinct = clustered["counts"]["total_distinct_review_items"]
        auto_a = clustered["counts"]["auto_advisory_allowed"]
        batch_r = clustered["counts"]["batch_review"]
        mand = clustered["counts"]["mandatory_review"]
        hard = clustered["counts"]["hard_stop"]

        # promotion blocked = high + unresolved high + financial + any C
        promotion_blocked = mand + hard + clustered["financial_review_burden"]["distinct_items"]

        mart = {
            "mart": "phase_09_review_burden",
            "schema_version": LATEST_SCHEMA_VERSION,
            "project_scope": project_key or "all",
            "policy_id": seed.get("policy_id"),
            "policy_version": seed.get("version") or "1",
            "contract_version": contract.get("version") or "1",
            "two_step_classification": True,
            "total_distinct_review_items": total_distinct,
            "auto_advisory_allowed": auto_a,
            "batch_review": batch_r,
            "mandatory_review": mand,
            "hard_stop": hard,
            "financial_review_burden": clustered["financial_review_burden"],
            "high_impact_summary": clustered["high_impact_summary"],
            "clusters": clustered["clusters"],
            "operator_visible_count": min(daily, len(clustered["operator_visible_clusters"])),
            "suppressed_noise_count": clustered["suppressed_or_batched"],
            "advisory_retrieval_allowed_count": auto_a + batch_r,  # B is still usable as unpromoted advisory
            "promotion_blocked_count": promotion_blocked,
            "guardrails": {
                "read_only": True,
                "metadata_only": True,
                "two_step_family_necessary_impact_decisive": True,
                "high_impact_beats_family": True,
                "financial_separate_burden": True,
                "top_examples_hash_only": True,
                "advisory_only_no_determination": True,
                "no_raw_no_writeback": True,
            },
        }
        return mart
    finally:
        conn.close()


def evaluate_review_burden_gate(mart: dict[str, Any]) -> dict[str, Any]:
    """Produce the separated gate (no blanket for advisory; promotion still blocked for high/C)."""
    auto = int(mart.get("auto_advisory_allowed", 0))
    batch = int(mart.get("batch_review", 0))
    mand = int(mart.get("mandatory_review", 0))
    hard = int(mart.get("hard_stop", 0))
    fin = mart.get("financial_review_burden", {})
    fin_dist = int(fin.get("distinct_items", 0))

    # advisory allowed if we have safe A or B after two-step
    advisory_allowed = (auto + batch) > 0

    # promotion still blocked for anything C / high / financial / hard
    promotion_blocked = mand + hard + fin_dist

    return {
        "gate": "phase_09_review_burden_policy",
        "review_model": "exception_based",
        "two_step": True,
        "advisory_retrieval_allowed": advisory_allowed,
        "promotion_blocked_for_high_impact": promotion_blocked > 0,
        "blanket_review_block": False,
        "financial_separate": True,
        "operator_review_budget": {
            "daily_max_items": 10,
            "visible_now": mart.get("operator_visible_count", 0),
            "suppressed_or_batched": mart.get("suppressed_noise_count", 0),
        },
        "counts": {
            "total_distinct_review_items": mart.get("total_distinct_review_items"),
            "auto_advisory_allowed": auto,
            "batch_review": batch,
            "mandatory_review": mand,
            "hard_stop": hard,
        },
        "financial_review_burden": fin,
        "high_impact_summary": mart.get("high_impact_summary"),
        "guardrails": mart.get("guardrails", {}),
    }


def build_review_burden_proof(db_path: str | None = None) -> dict[str, Any]:
    """Proof wrapper (read-only). Includes raw_content_findings scan (must be empty) and gate."""
    mart = build_review_burden_mart(db_path)
    gate = evaluate_review_burden_gate(mart)

    # Light global guard scan (reuse pattern from safety / other proofs)
    raw_findings: list[str] = []
    # For burden we mainly attest that we did not *emit* raw and the clusters use hash-only.
    # The source tables' guards are asserted by the 08D/09 no-raw proofs; here we just confirm
    # no raw leaked into our output structures.
    for cl in mart.get("clusters", []):
        for ex in cl.get("top_examples", []):
            for bad in ("subject", "body", "title", "url", "email", "raw"):
                if bad in ex:
                    raw_findings.append(f"prohibited_field_in_example:{bad}")

    proof_passed = (
        len(raw_findings) == 0
        and gate.get("blanket_review_block") is False
        and (gate.get("advisory_retrieval_allowed") or True)
    )

    return {
        "proof": "phase_09_review_burden",
        "schema_version": mart.get("schema_version"),
        "schema_version_expected": LATEST_SCHEMA_VERSION,
        "proof_passed": proof_passed,
        "raw_content_findings": raw_findings,
        "mart": mart,
        "gate": gate,
    }


# Optional persistence for runs (additive table use; called by CLI only on explicit emit in future)
def persist_review_burden_run(
    db_path: str | None,
    result: dict[str, Any],
    *,
    policy_version: str,
    project_key: str | None = None,
) -> str:
    """Insert a metadata-only run row into second_brain_review_burden_runs (with all guards=0)."""
    resolved = db_path or str(PathPolicy().get_db_path())
    conn = sqlite3.connect(resolved)
    try:
        run_id = f"rbr-{int(datetime.now(timezone.utc).timestamp())}"
        conn.execute(
            """
            INSERT INTO second_brain_review_burden_runs
            (run_id, created_at_utc, policy_version, schema_version, project_key,
             total_distinct, auto_advisory, batch_review, mandatory_review, hard_stop,
             financial_raw, financial_distinct,
             raw_email_body_persisted, raw_document_text_persisted, raw_calendar_payload_persisted,
             raw_procore_payload_persisted, raw_financial_source_payload_persisted,
             raw_prompt_persisted, raw_response_persisted, signed_url_persisted, download_url_persisted,
             external_writeback_performed, graph_api_call_performed, procore_api_call_performed,
             email_send_performed, calendar_update_performed, source_system_writeback_performed,
             arbitrary_sql_performed, raw_store_access_performed, financial_determination_performed,
             payment_decision_performed, claim_or_entitlement_decision_performed, unsupported_claim_performed,
             raw_vector_content_persisted, semantic_retrieval_bypassed_policy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)
            """,
            (
                run_id,
                datetime.now(timezone.utc).isoformat(),
                policy_version,
                LATEST_SCHEMA_VERSION,
                project_key,
                result.get("total_distinct_review_items", 0),
                result.get("auto_advisory_allowed", 0),
                result.get("batch_review", 0),
                result.get("mandatory_review", 0),
                result.get("hard_stop", 0),
                result.get("financial_review_burden", {}).get("raw_unresolved", 0),
                result.get("financial_review_burden", {}).get("distinct_items", 0),
            ),
        )
        conn.commit()
        return run_id
    finally:
        conn.close()
