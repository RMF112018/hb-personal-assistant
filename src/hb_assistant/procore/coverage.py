"""Local payload-coverage reporting for the ``procore live coverage`` command.

Runs an endpoint's normalizer over a locally-provided raw payload and reports
which raw top-level fields are captured into ``canonical_fields`` vs. not — names
and types only, never raw values (mirrors the Phase 04B Prompt 00
``payload-field-inventory`` posture). Purely local; no network, no DB.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from . import endpoints as ep_registry
from .live_sync import resolve_normalizer

# Containers normalizers attach to canonical_fields that are projections (entities,
# edges, action signals, text intelligence) rather than captured raw scalar fields.
_PROJECTION_KEYS = ("entities", "edges", "action_signals", "text_intelligence")
# Known raw->canonical renames so a renamed-but-captured field is not reported
# as uncaptured.
_ALIASES = {"html_url": "source_url", "url": "source_url"}
# Canonical field-name suffixes that denote a hash-only / redacted summary (never
# a raw value): see normalizers/hashing.py + financial.py (hash_summary, *_ref).
_HASH_ONLY_SUFFIXES = ("_summary", "_ref")


def _first_record(raw: Any) -> Mapping[str, Any]:
    """Reduce a payload (single dict / list / v2 ``{"data": [...]}`` envelope) to
    the first record dict."""
    if isinstance(raw, dict) and isinstance(raw.get("data"), list):
        raw = raw["data"]
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    if not isinstance(raw, dict):
        raise ValueError("payload does not contain a record object")
    return raw


def _is_captured(raw_key: str, canonical_keys: set[str]) -> bool:
    if raw_key in canonical_keys:
        return True
    if f"{raw_key}_summary" in canonical_keys or f"{raw_key}_id" in canonical_keys:
        return True
    if _ALIASES.get(raw_key) in canonical_keys:
        return True
    return any(
        ck.startswith(f"{raw_key}_") or ck.endswith(f"_{raw_key}") or f"_{raw_key}_" in ck
        for ck in canonical_keys
    )


def _count_entities(container: Any) -> int:
    if isinstance(container, dict):
        return sum(len(v) for v in container.values() if isinstance(v, list))
    if isinstance(container, list):
        return len(container)
    return 0


def _is_hash_only(key: str, value: Any) -> bool:
    """True when a canonical field is a hash-only / redacted summary (no raw value).

    Detected by the ``*_summary`` / ``*_ref`` naming convention or by the
    hash-summary value shape (``{type, length, hash_prefix}`` / ``{hash_prefix, ...}``).
    """
    if key.endswith(_HASH_ONLY_SUFFIXES):
        return True
    return isinstance(value, dict) and "hash_prefix" in value


def compute_payload_coverage(endpoint_id: str, raw: Any, *, now_utc: str) -> Dict[str, Any]:
    """Return a field-coverage report for ``raw`` under ``endpoint_id`` (names +
    types only — no raw values)."""
    normalizer = resolve_normalizer(endpoint_id)
    if normalizer is None:
        raise ValueError(f"no normalizer for endpoint {endpoint_id!r}")

    record_raw = _first_record(raw)
    normalized = normalizer(
        record_raw,
        project_key="coverage",
        endpoint_id=endpoint_id,
        correlation_id="coverage",
        fetched_at=now_utc,
    )
    canonical = normalized.get("canonical_fields") if isinstance(normalized, dict) else None
    canonical = canonical if isinstance(canonical, dict) else {}

    canonical_field_keys = [k for k in canonical if k not in _PROJECTION_KEYS]
    canonical_key_set = set(canonical_field_keys)

    raw_keys = sorted(record_raw)
    captured = sorted(k for k in raw_keys if _is_captured(k, canonical_key_set))
    uncaptured = sorted(k for k in raw_keys if k not in captured)

    # Classify the canonical output (names only) into hash-only summaries vs.
    # captured raw scalars, and record which projection containers are present.
    hash_only_fields = sorted(k for k in canonical_field_keys if _is_hash_only(k, canonical[k]))
    captured_scalar_fields = sorted(set(canonical_field_keys) - set(hash_only_fields))
    projected_containers = sorted(k for k in _PROJECTION_KEYS if k in canonical)

    meta = _normalizer_meta(endpoint_id)
    return {
        "endpoint_id": endpoint_id,
        "normalizer_name": meta["normalizer_name"],
        "normalizer_version": meta["normalizer_version"],
        "raw_field_count": len(raw_keys),
        "canonical_field_count": len(canonical_field_keys),
        "raw_field_paths": [{"path": k, "type": type(record_raw[k]).__name__} for k in raw_keys],
        "canonical_field_paths": sorted(canonical_field_keys),
        "captured": captured,
        "uncaptured": uncaptured,
        # Phase 06B Prompt 05 classification (names only):
        "captured_scalar_fields": captured_scalar_fields,
        "hash_only_fields": hash_only_fields,
        "intentionally_omitted_fields": uncaptured,
        "projected_containers": projected_containers,
        "coverage_ratio": round(len(captured) / len(raw_keys), 4) if raw_keys else 1.0,
        "entity_count": _count_entities(canonical.get("entities")),
        "edge_count": _count_entities(canonical.get("edges")),
        "action_signal_count": _count_entities(canonical.get("action_signals")),
        "no_raw_values_persisted": True,
    }


def _normalizer_meta(endpoint_id: str) -> Dict[str, Any]:
    """Resolve normalizer name + schema version for an endpoint (no values).

    ``normalizer_version`` is the ``NORMALIZATION_SCHEMA_VERSION`` declared by the
    resolved normalizer's module; ``registered`` is False for held endpoints with
    no normalizer (e.g. the budget-details sentinel).
    """
    fn = resolve_normalizer(endpoint_id)
    if fn is None:
        return {"registered": False, "normalizer_name": None, "normalizer_version": None}
    module = __import__(fn.__module__, fromlist=["NORMALIZATION_SCHEMA_VERSION"])
    return {
        "registered": True,
        "normalizer_name": fn.__name__,
        "normalizer_version": getattr(module, "NORMALIZATION_SCHEMA_VERSION", None),
    }


# Family -> projected entities/edges/signals/financial tables. Documented mapping
# derived from the store/procore_*_projection.py + procore_enrichment.py layer; an
# intelligence aid (coarse capability, not an authoritative per-record claim). A test
# guards that every registry family has an entry.
_FAMILY_PROJECTION: Dict[str, Dict[str, Any]] = {
    "foundation": {
        "entities": [],
        "edges": False,
        "action_signals": False,
        "text_intelligence": False,
        "financial_tables": [],
    },
    "rfis": {
        "entities": ["people", "company"],
        "edges": True,
        "action_signals": True,
        "text_intelligence": True,
        "financial_tables": [],
    },
    "submittals": {
        "entities": ["people", "company", "custom_fields"],
        "edges": True,
        "action_signals": True,
        "text_intelligence": True,
        "financial_tables": [],
    },
    "observations": {
        "entities": ["people", "custom_fields"],
        "edges": True,
        "action_signals": True,
        "text_intelligence": True,
        "financial_tables": [],
    },
    "meetings": {
        "entities": ["people", "attachments"],
        "edges": True,
        "action_signals": True,
        "text_intelligence": True,
        "financial_tables": [],
    },
    "daily_logs": {
        "entities": ["people", "company", "location", "attachments", "custom_fields"],
        "edges": True,
        "action_signals": True,
        "text_intelligence": True,
        "financial_tables": [],
    },
    "punch_items": {
        "entities": ["people", "custom_fields", "attachments"],
        "edges": True,
        "action_signals": True,
        "text_intelligence": True,
        "financial_tables": [],
    },
    "schedules": {
        "entities": [],
        "edges": True,
        "action_signals": True,
        "text_intelligence": False,
        "financial_tables": [],
    },
    "inspections": {
        "entities": ["people"],
        "edges": True,
        "action_signals": True,
        "text_intelligence": True,
        "financial_tables": [],
    },
    "owner_contracts": {
        "entities": ["company"],
        "edges": True,
        "action_signals": True,
        "text_intelligence": False,
        "financial_tables": [
            "procore_financial_contracts",
            "procore_financial_line_items",
            "procore_financial_amount_facts",
        ],
    },
    "owner_billing": {
        "entities": [],
        "edges": True,
        "action_signals": True,
        "text_intelligence": False,
        "financial_tables": ["procore_financial_amount_facts"],
    },
    "commitments": {
        "entities": ["company"],
        "edges": True,
        "action_signals": True,
        "text_intelligence": False,
        "financial_tables": [
            "procore_financial_contracts",
            "procore_financial_line_items",
            "procore_financial_compliance_documents",
            "procore_financial_amount_facts",
        ],
    },
    "purchase_orders": {
        "entities": ["company"],
        "edges": True,
        "action_signals": True,
        "text_intelligence": False,
        "financial_tables": [
            "procore_financial_contracts",
            "procore_financial_line_items",
            "procore_financial_amount_facts",
        ],
    },
    "subcontractor_invoices": {
        "entities": ["company"],
        "edges": True,
        "action_signals": True,
        "text_intelligence": False,
        "financial_tables": [
            "procore_financial_subcontractor_invoices",
            "procore_financial_invoice_items",
            "procore_financial_amount_facts",
        ],
    },
    "billing": {
        "entities": [],
        "edges": True,
        "action_signals": True,
        "text_intelligence": False,
        "financial_tables": ["procore_financial_billing_periods"],
    },
    "budget": {
        "entities": [],
        "edges": True,
        "action_signals": True,
        "text_intelligence": False,
        "financial_tables": [
            "procore_financial_budget_views",
            "procore_financial_budget_rows",
            "procore_financial_budget_changes",
            "procore_financial_amount_facts",
        ],
    },
    "change_management": {
        "entities": ["company"],
        "edges": True,
        "action_signals": True,
        "text_intelligence": False,
        "financial_tables": [
            "procore_financial_rfqs",
            "procore_financial_change_events",
            "procore_financial_amount_facts",
        ],
    },
}


def _coverage_for_payload(
    endpoint_id: str, payloads_dir: Path, now_utc: str
) -> Optional[Dict[str, Any]]:
    """Run coverage if a local ``<endpoint_id>.json`` sample exists (names only)."""
    sample = payloads_dir / f"{endpoint_id}.json"
    if not sample.is_file():
        return None
    raw = json.loads(sample.read_text(encoding="utf-8"))
    report = compute_payload_coverage(endpoint_id, raw, now_utc=now_utc)
    return {
        "captured_scalar_fields": report["captured_scalar_fields"],
        "hash_only_fields": report["hash_only_fields"],
        "intentionally_omitted_fields": report["intentionally_omitted_fields"],
        "projected_containers": report["projected_containers"],
        "raw_field_count": report["raw_field_count"],
        "canonical_field_count": report["canonical_field_count"],
        "entity_count": report["entity_count"],
        "edge_count": report["edge_count"],
        "action_signal_count": report["action_signal_count"],
        "no_raw_values_persisted": True,
    }


def build_coverage_matrix(*, payloads_dir: Optional[Path], now_utc: str) -> Dict[str, Any]:
    """Endpoint coverage matrix grouped by family (names/types/counts only).

    Every endpoint emits a contract row (normalizer name/version, family projection
    targets, sensitivity, held status). Endpoints with a local ``<id>.json`` sample
    under ``payloads_dir`` are additionally enriched with captured/hash-only/omitted
    field NAMES and entity/edge/signal counts. No raw values are ever read into the
    matrix output.
    """
    families: Dict[str, Dict[str, Any]] = {}
    sampled = 0
    for adapter in sorted(ep_registry.list_all(), key=lambda a: (a.family, a.endpoint_id)):
        meta = _normalizer_meta(adapter.endpoint_id)
        row: Dict[str, Any] = {
            "endpoint_id": adapter.endpoint_id,
            "family": adapter.family,
            "sensitivity": adapter.sensitivity,
            "review_required_default": adapter.review_required_default,
            "live_verified": adapter.live_verified,
            "promotion_status": "promoted" if adapter.live_verified else "held",
            "normalizer": meta,
            "projection": _FAMILY_PROJECTION.get(adapter.family),
        }
        coverage = (
            _coverage_for_payload(adapter.endpoint_id, payloads_dir, now_utc)
            if payloads_dir is not None and meta["registered"]
            else None
        )
        if coverage is not None:
            row["payload_source"] = "fixture"
            row["coverage"] = coverage
            sampled += 1
        else:
            row["payload_source"] = "none"
            row["coverage"] = "contract_only"
        fam = families.setdefault(adapter.family, {"endpoint_count": 0, "endpoints": []})
        fam["endpoint_count"] += 1
        fam["endpoints"].append(row)

    return {
        "command": "hb-assistant procore live coverage-matrix",
        "ok": True,
        "phase": "Phase 06B Prompt 05",
        "family_count": len(families),
        "endpoint_count": sum(f["endpoint_count"] for f in families.values()),
        "fixture_sampled_count": sampled,
        "families": families,
        "no_raw_values_persisted": True,
    }


__all__ = ["compute_payload_coverage", "build_coverage_matrix", "_FAMILY_PROJECTION"]
