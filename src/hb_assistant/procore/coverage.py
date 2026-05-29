"""Local payload-coverage reporting for the ``procore live coverage`` command.

Runs an endpoint's normalizer over a locally-provided raw payload and reports
which raw top-level fields are captured into ``canonical_fields`` vs. not — names
and types only, never raw values (mirrors the Phase 04B Prompt 00
``payload-field-inventory`` posture). Purely local; no network, no DB.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from .live_sync import resolve_normalizer

# Containers the daily-log normalizers attach to canonical_fields that are
# projections rather than captured raw fields.
_PROJECTION_KEYS = ("entities", "edges", "action_signals")
# Known raw->canonical renames so a renamed-but-captured field is not reported
# as uncaptured.
_ALIASES = {"html_url": "source_url", "url": "source_url"}


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

    return {
        "endpoint_id": endpoint_id,
        "raw_field_count": len(raw_keys),
        "canonical_field_count": len(canonical_field_keys),
        "raw_field_paths": [{"path": k, "type": type(record_raw[k]).__name__} for k in raw_keys],
        "canonical_field_paths": sorted(canonical_field_keys),
        "captured": captured,
        "uncaptured": uncaptured,
        "coverage_ratio": round(len(captured) / len(raw_keys), 4) if raw_keys else 1.0,
        "entity_count": _count_entities(canonical.get("entities")),
        "edge_count": _count_entities(canonical.get("edges")),
        "action_signal_count": _count_entities(canonical.get("action_signals")),
        "no_raw_values_persisted": True,
    }


__all__ = ["compute_payload_coverage"]
