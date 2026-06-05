"""Phase 07D Prompt 08 — review-controlled risk-digest materialization.

Materializes `project_risk_digest_items` (V25, shipped empty in Prompt 02) by classifying local
risk indicators into the four policy `risk_source_class` values
(`risk_digest_policy.seed.yaml`):

- ``source_stated``     — Procore explicitly raised the condition (``procore_action_signals``).
- ``inferred_candidate``— deterministic/strong grouped issue families that are risk-bearing
                          (``project_issue_history_items``: overdue/void/rejected or aged).
- ``review_required``   — weak / sensitive / disputed relationship candidates.
- ``model_proposed``    — model-derived relationship candidates (never auto-promoted).

The digest is bounded: one item per ``(risk_source_class, risk_indicator_type)`` with a count and
safe sample references — not one row per underlying record. Indicators whose mapped category is in
``review_required_categories`` (legal/claim/contractual/safety/personnel/financial/schedule_impact/
cost_impact) are flagged ``review_required``; model/weak/sensitive items are always review-required
and are never auto-promoted.

Guardrails: local-first, read-only against external systems; refs are local ids / hashes / Procore
endpoint names; no raw email/document/calendar content, raw status/title payload, signed/download
URL, token, secret, prompt, or response is read or persisted; outputs are advisory and emit no final
legal/contractual/claim/safety/financial determination.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from hb_assistant.construction.relationships.contracts import (
    load_phase_07d_contract,
    load_phase_07d_seed,
)
from hb_assistant.construction.store.repositories import ConstructionStore
from hb_assistant.normalize.redaction import hash_value
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

_RISK_DIGEST_GUARDRAILS: dict[str, Any] = {
    "external_systems": "read_only",
    "writeback": "none",
    "writes": "local_sqlite_project_risk_digest_items_only",
    "no_raw_content": True,
    "refs_are_local_ids_or_hashes": True,
    "advisory_only": True,
    "no_final_determinations": True,
    "auto_promotion": False,
}

# Issue-history statuses / age that make a family risk-bearing (inferred_candidate).
_RISK_ISSUE_STATUSES = frozenset({"overdue", "void", "rejected", "out_for_pricing"})
_AGING_THRESHOLD_DAYS = 31

# Keyword → review_required_category map (substring match on the indicator type).
_CATEGORY_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("safety", "safety"),
    ("inspection", "safety"),
    ("incident", "safety"),
    ("injury", "safety"),
    ("deficien", "safety"),
    ("claim", "claim"),
    ("dispute", "claim"),
    ("lien", "claim"),
    ("backcharge", "claim"),
    ("legal", "legal"),
    ("invoice", "financial"),
    ("payment", "financial"),
    ("budget", "financial"),
    ("billing", "financial"),
    ("retainage", "financial"),
    ("financial", "financial"),
    ("unpaid", "financial"),
    ("cost", "cost_impact"),
    ("schedule", "schedule_impact"),
    ("overdue", "schedule_impact"),
    ("delay", "schedule_impact"),
    ("aging", "schedule_impact"),
    ("due", "schedule_impact"),
    ("commitment", "contractual"),
    ("contract", "contractual"),
    ("change_order", "contractual"),
    ("change_event", "contractual"),
    ("unexecuted", "contractual"),
    ("notice", "contractual"),
    ("personnel", "personnel"),
    ("assignee", "personnel"),
)


def _risk_category(indicator: str, categories: frozenset[str]) -> Optional[str]:
    """Map a risk indicator type to a review_required_category, else None."""
    low = indicator.lower()
    for keyword, category in _CATEGORY_KEYWORDS:
        if keyword in low and category in categories:
            return category
    return None


def _endpoint_of(record_ref: Any) -> Optional[str]:
    """Procore endpoint segment of a record_key `project|endpoint|parent|id`, else None."""
    s = str(record_ref or "")
    parts = s.split("|")
    return parts[1] if len(parts) >= 4 and parts[1] else None


class RiskDigestBuilder:
    """Materialize review-controlled risk digests from local risk-signal sources (V25)."""

    def __init__(self, store: Optional[ConstructionStore] = None) -> None:
        self._store = store or ConstructionStore()
        contract = load_phase_07d_contract("risk_digest_contract")
        self._contract_version = contract.get("version")
        policy = load_phase_07d_seed("risk_digest_policy")
        self._policy_version = policy.get("version")
        self._review_categories = frozenset(policy.get("review_required_categories", []))

    def _discover_projects(self, project_filter: Optional[str]) -> list[str]:
        if project_filter is not None:
            return [project_filter]
        keys: set[str] = set()
        for c in self._store.list_cross_source_relationship_candidates(limit=100000):
            if c.get("project_key"):
                keys.add(str(c["project_key"]))
        for it in self._store.list_project_issue_history_items(limit=100000):
            if it.get("project_key"):
                keys.add(str(it["project_key"]))
        for sig in self._store.list_procore_action_signals(signal_status="open"):
            if sig.get("project_key"):
                keys.add(str(sig["project_key"]))
        return sorted(keys)

    # -- public API ----------------------------------------------------------

    def build(
        self, *, dry_run: bool = True, project_filter: Optional[str] = None
    ) -> dict[str, Any]:
        """Materialize the per-project risk digest. Dry-run plans counts and writes nothing;
        --apply upserts one row per (risk_source_class, risk_indicator_type)."""
        mode = "apply" if not dry_run else "dry_run"
        projects = self._discover_projects(project_filter)
        items_planned = 0
        items_written = 0
        review_required_total = 0
        by_source_class: dict[str, int] = {}
        by_indicator: dict[str, int] = {}
        by_confidence: dict[str, int] = {}

        for project_key in projects:
            for item in self._project_items(project_key):
                items_planned += 1
                by_source_class[item["risk_source_class"]] = (
                    by_source_class.get(item["risk_source_class"], 0) + 1
                )
                by_indicator[item["risk_indicator_type"]] = (
                    by_indicator.get(item["risk_indicator_type"], 0) + 1
                )
                by_confidence[item["confidence_class"]] = (
                    by_confidence.get(item["confidence_class"], 0) + 1
                )
                if item["review_required"]:
                    review_required_total += 1
                if not dry_run:
                    self._store.upsert_project_risk_digest_item(
                        risk_digest_id=item["risk_digest_id"],
                        project_key=project_key,
                        risk_indicator_type=item["risk_indicator_type"],
                        risk_source_class=item["risk_source_class"],
                        summary_redacted=item["summary_redacted"],
                        confidence_class=item["confidence_class"],
                        evidence_trail_id=item["evidence_trail_id"],
                        review_required=item["review_required"],
                        stale_unknown_flags_json=item["stale_unknown_flags_json"],
                    )
                    items_written += 1

        return {
            "command": "construction-agent risk-digest build",
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
                "by_risk_source_class": dict(sorted(by_source_class.items())),
                "by_risk_indicator_type": dict(sorted(by_indicator.items())),
                "by_confidence_class": dict(sorted(by_confidence.items())),
            },
            "guardrails": _RISK_DIGEST_GUARDRAILS,
        }

    # -- classifier passes ---------------------------------------------------

    def _project_items(self, project_key: str) -> list[dict[str, Any]]:
        return [
            *self._source_stated_items(project_key),
            *self._inferred_items(project_key),
            *self._relationship_items(project_key),
        ]

    def _make_item(
        self,
        project_key: str,
        risk_source_class: str,
        indicator: str,
        *,
        count: int,
        confidence_class: str,
        evidence_trail_id: Optional[str],
        sample_refs: list[str],
        always_review: bool = False,
    ) -> dict[str, Any]:
        category = _risk_category(indicator, self._review_categories)
        review_required = always_review or category is not None
        summary = {
            "indicator": indicator,
            "source_class": risk_source_class,
            "count": count,
            "category": category,
            "sample_refs": sorted(set(sample_refs))[:5],
        }
        flags = {"category": category} if category else None
        return {
            "risk_digest_id": hash_value(f"risk|{project_key}|{risk_source_class}|{indicator}")
            or f"{risk_source_class}:{indicator}",
            "risk_indicator_type": indicator,
            "risk_source_class": risk_source_class,
            "summary_redacted": json.dumps(summary, sort_keys=True),
            "confidence_class": confidence_class,
            "evidence_trail_id": evidence_trail_id,
            "review_required": review_required,
            "stale_unknown_flags_json": json.dumps(flags, sort_keys=True) if flags else None,
        }

    def _source_stated_items(self, project_key: str) -> list[dict[str, Any]]:
        """One item per open Procore action-signal type (Procore explicitly stated it)."""
        groups: dict[str, list[str]] = {}
        for sig in self._store.list_procore_action_signals(
            project_key=project_key, signal_status="open"
        ):
            stype = str(sig.get("signal_type"))
            endpoint = sig.get("endpoint_id") or _endpoint_of(sig.get("record_key"))
            groups.setdefault(stype, [])
            if endpoint:
                groups[stype].append(str(endpoint))
        return [
            self._make_item(
                project_key,
                "source_stated",
                stype,
                count=len(refs) if refs else 1,
                confidence_class="deterministic",
                evidence_trail_id=None,
                sample_refs=refs,
            )
            for stype, refs in sorted(groups.items())
        ]

    def _inferred_items(self, project_key: str) -> list[dict[str, Any]]:
        """Risk-bearing issue families grouped into inferred risk indicators."""
        buckets: dict[str, dict[str, Any]] = {}
        for it in self._store.list_project_issue_history_items(
            project_key=project_key, limit=100000
        ):
            status = str(it.get("status") or "")
            aged = int(it.get("age_days") or 0) >= _AGING_THRESHOLD_DAYS
            if status in _RISK_ISSUE_STATUSES:
                indicator = f"{status}_issue"
            elif aged and status in ("open", "pending", "draft", "initiated", "unknown"):
                indicator = "aging_open_issue"
            else:
                continue
            b = buckets.setdefault(
                indicator, {"count": 0, "refs": [], "trail": None, "review": False}
            )
            b["count"] += 1
            if it.get("issue_kind"):
                b["refs"].append(str(it["issue_kind"]))
            b["trail"] = b["trail"] or it.get("evidence_trail_id")
            b["review"] = b["review"] or bool(it.get("review_required"))
        return [
            self._make_item(
                project_key,
                "inferred_candidate",
                indicator,
                count=b["count"],
                confidence_class="strong_heuristic",
                evidence_trail_id=b["trail"],
                sample_refs=b["refs"],
                always_review=b["review"],
            )
            for indicator, b in sorted(buckets.items())
        ]

    def _relationship_items(self, project_key: str) -> list[dict[str, Any]]:
        """review_required (weak/sensitive) and model_proposed relationship risk indicators."""
        review: dict[str, dict[str, Any]] = {}
        model: dict[str, dict[str, Any]] = {}
        for c in self._store.list_cross_source_relationship_candidates(
            project_key=project_key, limit=100000
        ):
            rtype = str(c.get("relationship_type"))
            trail = c.get("evidence_trail_id")
            if c.get("model_proposed"):
                b = model.setdefault(rtype, {"count": 0, "trail": None})
                b["count"] += 1
                b["trail"] = b["trail"] or trail
            elif c.get("sensitive_high_impact"):
                b = review.setdefault(
                    "sensitive_high_impact_relationship", {"count": 0, "trail": None}
                )
                b["count"] += 1
                b["trail"] = b["trail"] or trail
            elif c.get("review_required") or c.get("confidence_class") == "weak_heuristic":
                b = review.setdefault(rtype, {"count": 0, "trail": None})
                b["count"] += 1
                b["trail"] = b["trail"] or trail
        items = [
            self._make_item(
                project_key,
                "review_required",
                indicator,
                count=b["count"],
                confidence_class="weak_heuristic",
                evidence_trail_id=b["trail"],
                sample_refs=[],
                always_review=True,
            )
            for indicator, b in sorted(review.items())
        ]
        items += [
            self._make_item(
                project_key,
                "model_proposed",
                indicator,
                count=b["count"],
                confidence_class="model_proposed",
                evidence_trail_id=b["trail"],
                sample_refs=[],
                always_review=True,
            )
            for indicator, b in sorted(model.items())
        ]
        return items


def project_risk_digest_status(
    store: Optional[ConstructionStore] = None, *, project_filter: Optional[str] = None
) -> dict[str, Any]:
    """Read-only coverage report over the V25 project risk-digest table."""
    store = store or ConstructionStore()
    items = store.list_project_risk_digest_items(project_key=project_filter, limit=100000)
    by_source_class: dict[str, int] = {}
    by_indicator: dict[str, int] = {}
    by_confidence: dict[str, int] = {}
    review_required = 0
    for it in items:
        by_source_class[str(it["risk_source_class"])] = (
            by_source_class.get(str(it["risk_source_class"]), 0) + 1
        )
        by_indicator[str(it["risk_indicator_type"])] = (
            by_indicator.get(str(it["risk_indicator_type"]), 0) + 1
        )
        by_confidence[str(it["confidence_class"])] = (
            by_confidence.get(str(it["confidence_class"]), 0) + 1
        )
        if it["review_required"]:
            review_required += 1
    return {
        "command": "construction-agent risk-digest status",
        "ok": True,
        "schema_version": LATEST_SCHEMA_VERSION,
        "project_filter": project_filter,
        "summary": {
            "items": len(items),
            "review_required": review_required,
            "by_risk_source_class": dict(sorted(by_source_class.items())),
            "by_risk_indicator_type": dict(sorted(by_indicator.items())),
            "by_confidence_class": dict(sorted(by_confidence.items())),
        },
        "guardrails": _RISK_DIGEST_GUARDRAILS,
    }
