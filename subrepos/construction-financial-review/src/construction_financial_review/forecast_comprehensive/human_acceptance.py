"""Human-acceptance stamping + review-queue assembly.

Integrated recommendations are never represented as accepted: every posture-changing row defaults to
acceptance_status=pending with null accepted_by/at/notes. There is no live acceptance store; this package
only proposes.
"""
from __future__ import annotations

from collections import OrderedDict


def acceptance_fields() -> list:
    return [("requires_human_acceptance", True), ("do_not_auto_apply", True),
            ("acceptance_status", "pending"), ("accepted_by", None),
            ("accepted_at", None), ("acceptance_notes", None)]


def stamp(od: OrderedDict) -> OrderedDict:
    for k, v in acceptance_fields():
        od[k] = v
    return od


def review_item(project_key, key, cost_code, priority, reason, families) -> OrderedDict:
    row = OrderedDict([
        ("project_key", project_key), ("budget_code_key", key), ("cost_code", cost_code),
        ("review_priority", priority), ("review_reason", reason),
        ("affected_evidence_families", families),
    ])
    return stamp(row)
