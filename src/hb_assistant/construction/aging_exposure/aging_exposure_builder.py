"""Phase 07D Prompt 09 — aging & exposure reporting.

Materializes `aging_exposure_report_items` (V25, shipped empty in Prompt 02): one classified row per
Procore record across all record families, assigning each record an aging ``threshold_band`` from
``aging_exposure_thresholds.seed.yaml`` (current / monitor / aging / stale / critical_review) plus
``stale_flag`` and ``missing_status_flag``.

"Exposure" is aging-based — records aging into the stale / critical_review bands are the exposure.
"Financial boundaries": financial record families (budget / commitment / invoice / change-order /
billing / prime / purchase-order) are recognized and a financial-family record in a stale/critical
band is flagged ``review_required`` and surfaced in the report's financial-exposure summary; raw
financial amounts are **never** persisted (the table has no amount column — that is the boundary).

When a record carries no source ``updated_at_utc``, age is unknown: ``threshold_band="unknown"``,
``confidence_class=NULL`` — never overstated.

Guardrails: local-first, read-only against external systems; ``record_ref`` is a local stable record
key; ``status`` is a normalized bounded token (Procore dict-string statuses are parsed, never
persisted raw); no raw body / status payload / financial amount / signed-download URL / token /
secret is read or persisted; outputs are advisory and emit no final legal/contractual/claim/safety/
financial determination.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from hb_assistant.construction.relationships.contracts import (
    load_phase_07d_contract,
    load_phase_07d_seed,
)
from hb_assistant.construction.store.repositories import ConstructionStore
from hb_assistant.normalize.redaction import hash_value
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

_AGING_EXPOSURE_GUARDRAILS: dict[str, Any] = {
    "external_systems": "read_only",
    "writeback": "none",
    "writes": "local_sqlite_aging_exposure_report_items_only",
    "no_raw_content": True,
    "no_financial_amounts_persisted": True,
    "refs_are_local_ids_or_hashes": True,
    "advisory_only": True,
    "no_final_determinations": True,
    "auto_promotion": False,
}

_STALE_BANDS = frozenset({"stale", "critical_review"})

# Record-family keywords that denote a financial family (financial-exposure boundary).
_FINANCIAL_KEYWORDS = (
    "budget", "commitment", "invoice", "change-order", "change_order", "change-event",
    "change_event", "billing", "prime", "purchase-order", "purchase_order", "payment",
    "contract", "compliance",
)

_KNOWN_STATUS = frozenset(
    {
        "open", "closed", "approved", "draft", "void", "pending", "none", "rejected",
        "in_review", "submitted", "answered", "overdue", "initiated", "out_for_pricing",
        "active", "complete", "incomplete",
    }
)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _normalize_status(raw: Any) -> str:
    """Map a source status to a bounded safe token; never persists the raw payload."""
    if raw is None:
        return "unknown"
    s = str(raw).strip()
    if not s:
        return "unknown"
    if s.startswith("{"):
        m = re.search(r"'mapped_to_status'\s*:\s*'([^']+)'", s) or re.search(
            r"'name'\s*:\s*'([^']+)'", s
        )
        s = m.group(1) if m else "other"
    s = s.lower().replace(" ", "_")
    if s in _KNOWN_STATUS:
        return s
    if len(s) <= 20 and s.replace("_", "").replace("-", "").isalnum():
        return s
    return "other"


def _is_financial(record_family: str) -> bool:
    low = record_family.lower()
    return any(k in low for k in _FINANCIAL_KEYWORDS)


def _procore_record_key(rec: dict[str, Any]) -> str:
    return "|".join(
        [
            str(rec.get("project_key") or ""),
            str(rec.get("endpoint_id") or ""),
            str(rec.get("parent_procore_id") or ""),
            str(rec.get("procore_record_id") or ""),
        ]
    )


class AgingExposureBuilder:
    """Materialize per-record aging & exposure classification (V25)."""

    def __init__(self, store: Optional[ConstructionStore] = None) -> None:
        self._store = store or ConstructionStore()
        contract = load_phase_07d_contract("aging_exposure_report_contract")
        self._contract_version = contract.get("version")
        policy = load_phase_07d_seed("aging_exposure_thresholds")
        self._policy_version = policy.get("version")
        self._default_bands = policy.get("default_bands", {})
        self._family_overrides = policy.get("record_family_overrides", {})

    # -- band assignment -----------------------------------------------------

    def _bands_for_family(self, record_family: str) -> dict[str, Any]:
        override = self._family_overrides.get(record_family)
        return override if isinstance(override, dict) and override else self._default_bands

    def _band_for(self, age_days: Optional[int], record_family: str) -> str:
        if age_days is None:
            return "unknown"
        bands = self._bands_for_family(record_family)
        for name, window in bands.items():
            if not isinstance(window, dict):
                continue
            lo = window.get("min_days")
            hi = window.get("max_days")
            lo = 0 if lo is None else int(lo)
            if age_days < lo:
                continue
            if hi is None or age_days <= int(hi):
                return str(name)
        return "unknown"

    def _discover_projects(self, project_filter: Optional[str]) -> list[str]:
        if project_filter is not None:
            return [project_filter]
        keys: set[str] = set()
        for rec in self._store.list_procore_live_records():
            if rec.get("project_key"):
                keys.add(str(rec["project_key"]))
        return sorted(keys)

    def _evidence_map(self, project_key: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for c in self._store.list_cross_source_relationship_candidates(
            project_key=project_key, limit=100000
        ):
            ref = c.get("source_record_ref")
            trail = c.get("evidence_trail_id")
            if ref and trail and str(ref) not in out:
                out[str(ref)] = str(trail)
        return out

    # -- public API ----------------------------------------------------------

    def build(
        self,
        *,
        dry_run: bool = True,
        project_filter: Optional[str] = None,
        now_utc: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Materialize per-record aging/exposure rows. Dry-run plans counts and writes nothing;
        --apply upserts one row per record (keyed by project + record_family + record_ref)."""
        mode = "apply" if not dry_run else "dry_run"
        now = now_utc or datetime.now(timezone.utc)
        projects = self._discover_projects(project_filter)

        items_planned = 0
        items_written = 0
        review_required_total = 0
        stale_total = 0
        missing_status_total = 0
        unknown_age_total = 0
        by_band: dict[str, int] = {}
        by_family: dict[str, int] = {}
        fin_stale = 0
        fin_critical = 0
        fin_total = 0

        for project_key in projects:
            evidence = self._evidence_map(project_key)
            for rec in self._store.list_procore_live_records(project_key=project_key):
                items_planned += 1
                item = self._build_item(project_key, rec, evidence, now)
                by_band[item["threshold_band"]] = by_band.get(item["threshold_band"], 0) + 1
                by_family[item["record_family"]] = by_family.get(item["record_family"], 0) + 1
                if item["review_required"]:
                    review_required_total += 1
                if item["stale_flag"]:
                    stale_total += 1
                if item["missing_status_flag"]:
                    missing_status_total += 1
                if item["threshold_band"] == "unknown":
                    unknown_age_total += 1
                if _is_financial(item["record_family"]):
                    fin_total += 1
                    if item["threshold_band"] == "stale":
                        fin_stale += 1
                    elif item["threshold_band"] == "critical_review":
                        fin_critical += 1
                if not dry_run:
                    self._store.upsert_aging_exposure_report_item(
                        aging_item_id=item["aging_item_id"], project_key=project_key,
                        record_family=item["record_family"], record_ref=item["record_ref"],
                        status=item["status"], threshold_band=item["threshold_band"],
                        age_days=item["age_days"], stale_flag=item["stale_flag"],
                        missing_status_flag=item["missing_status_flag"],
                        evidence_trail_id=item["evidence_trail_id"],
                        confidence_class=item["confidence_class"],
                        review_required=item["review_required"],
                    )
                    items_written += 1

        return {
            "command": "construction-agent aging-exposure build",
            "mode": mode,
            "ok": True,
            "schema_version": LATEST_SCHEMA_VERSION,
            "contract_version": self._contract_version,
            "policy_version": self._policy_version,
            "project_filter": project_filter,
            "summary": {
                "projects": projects,
                "items_planned": items_planned,
                "items_written": items_written,
                "review_required": review_required_total,
                "stale": stale_total,
                "missing_status": missing_status_total,
                "unknown_age": unknown_age_total,
                "by_threshold_band": dict(sorted(by_band.items())),
                "by_record_family": dict(sorted(by_family.items())),
                "financial_exposure": {
                    "total_financial": fin_total,
                    "stale": fin_stale,
                    "critical_review": fin_critical,
                },
            },
            "guardrails": _AGING_EXPOSURE_GUARDRAILS,
        }

    def _build_item(
        self,
        project_key: str,
        rec: dict[str, Any],
        evidence: dict[str, str],
        now: datetime,
    ) -> dict[str, Any]:
        record_family = str(rec.get("endpoint_id") or "unknown")
        record_ref = _procore_record_key(rec)
        raw_status = rec.get("status")
        status = _normalize_status(raw_status)
        missing_status = raw_status is None or str(raw_status).strip() == "" or status in (
            "unknown", "none",
        )
        dt = _parse_dt(rec.get("updated_at_utc"))
        if dt is None:
            age_days: Optional[int] = None
            confidence_class: Optional[str] = None
        else:
            age_days = max(0, (now - dt).days)
            confidence_class = "deterministic"
        band = self._band_for(age_days, record_family)
        stale_flag = band in _STALE_BANDS
        financial = _is_financial(record_family)
        review_required = (
            band == "critical_review"
            or (financial and stale_flag)
            or bool(rec.get("review_required"))
            or bool(rec.get("sensitive_reason"))
        )
        return {
            "aging_item_id": hash_value(f"aging|{project_key}|{record_family}|{record_ref}")
            or record_ref,
            "record_family": record_family,
            "record_ref": record_ref,
            "status": status,
            "age_days": age_days if age_days is not None else 0,
            "threshold_band": band,
            "stale_flag": stale_flag,
            "missing_status_flag": missing_status,
            "evidence_trail_id": evidence.get(record_ref),
            "confidence_class": confidence_class,
            "review_required": review_required,
        }


def project_aging_exposure_status(
    store: Optional[ConstructionStore] = None, *, project_filter: Optional[str] = None
) -> dict[str, Any]:
    """Read-only coverage report over the V25 aging & exposure table."""
    store = store or ConstructionStore()
    items = store.list_aging_exposure_report_items(project_key=project_filter, limit=100000)
    by_band: dict[str, int] = {}
    by_family: dict[str, int] = {}
    review_required = 0
    stale = 0
    missing_status = 0
    fin_total = 0
    fin_stale = 0
    fin_critical = 0
    for it in items:
        by_band[str(it["threshold_band"])] = by_band.get(str(it["threshold_band"]), 0) + 1
        by_family[str(it["record_family"])] = by_family.get(str(it["record_family"]), 0) + 1
        if it["review_required"]:
            review_required += 1
        if it["stale_flag"]:
            stale += 1
        if it["missing_status_flag"]:
            missing_status += 1
        if _is_financial(str(it["record_family"])):
            fin_total += 1
            if it["threshold_band"] == "stale":
                fin_stale += 1
            elif it["threshold_band"] == "critical_review":
                fin_critical += 1
    return {
        "command": "construction-agent aging-exposure status",
        "ok": True,
        "schema_version": LATEST_SCHEMA_VERSION,
        "project_filter": project_filter,
        "summary": {
            "items": len(items),
            "review_required": review_required,
            "stale": stale,
            "missing_status": missing_status,
            "by_threshold_band": dict(sorted(by_band.items())),
            "by_record_family": dict(sorted(by_family.items())),
            "financial_exposure": {
                "total_financial": fin_total,
                "stale": fin_stale,
                "critical_review": fin_critical,
            },
        },
        "guardrails": _AGING_EXPOSURE_GUARDRAILS,
    }
