"""Models, enums, deterministic identity, bounded caps, and the fixed advisory policy for the N8C-20
quality/evaluation layer.

Neutral and deterministic (no DB, no vault, no model, NO LLM, no network). Enum tuples are re-exported from
the V111 schema module so DB ``CHECK`` constraints and the Python layer can never drift. A quality finding
stores only a bounded ``detail`` / ``advice`` (a restated observation + an advisory review suggestion) +
preserved provenance ids + copied review/effective state — never a raw source/card/vault/email body, a full
upstream payload, or a raw prompt/response.

A quality run is a materialized, read-only EVALUATION product built from ONE existing N8C target. It NEVER
executes, repairs, stages, or writes a review disposition: every run + finding is pinned to
``action_policy='no_execution'`` / ``execution_policy='evaluate_only'`` / ``review_policy='advisory_review_loop'``
/ ``requires_operator_review=1``. ``evaluated`` is a run-record lifecycle status ONLY. Findings are advisory —
they may RECOMMEND operator review but never set/imply/mutate a disposition. Determinism makes re-evaluation
idempotent; a changed target (new ``target_digest``) yields a new ``quality_run_id`` (the prior run of the same
target + policy lineage is superseded by the repository — a quality-owned row only).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from hb_assistant.store.assistant_quality_tables import (
    QUALITY_EVENT_TYPE_VALUES,
    QUALITY_FINDING_TYPE_VALUES,
    QUALITY_RUN_STATUS_VALUES,
    QUALITY_SEVERITY_VALUES,
    QUALITY_TARGET_KIND_VALUES,
)

from .memory_models import bound_text, sha256_hex

# Bump when the evaluate / serialization contract changes — folded into every id.
QUALITY_EVALUATOR_VERSION = "quality-v1"

QUALITY_TARGET_KINDS = frozenset(QUALITY_TARGET_KIND_VALUES)
QUALITY_RUN_STATUSES = frozenset(QUALITY_RUN_STATUS_VALUES)
QUALITY_FINDING_TYPES = frozenset(QUALITY_FINDING_TYPE_VALUES)
QUALITY_SEVERITIES = frozenset(QUALITY_SEVERITY_VALUES)
EVENT_TYPES = frozenset(QUALITY_EVENT_TYPE_VALUES)

# Named severities.
SEVERITY_INFO = "info"
SEVERITY_WARN = "warn"
SEVERITY_RISK = "risk"

# --- fixed policy constants (never overridable; pinned by schema CHECK + asserted by tests) --------------
ACTION_POLICY = "no_execution"
EXECUTION_POLICY = "evaluate_only"
REVIEW_POLICY = "advisory_review_loop"
SOURCE_POLICY = "preserve_source_truth"
CITATION_POLICY = "preserve_citations"

QUALITY_POLICY_BLOCK = {
    "action_policy": ACTION_POLICY,
    "execution_policy": EXECUTION_POLICY,
    "review_policy": REVIEW_POLICY,
    "source_policy": SOURCE_POLICY,
    "citation_policy": CITATION_POLICY,
    "requires_operator_review": 1,
}

# --- bounded hard caps ----------------------------------------------------------------------------------
DETAIL_HARD_CAP = 1_000
ADVICE_HARD_CAP = 500
LABEL_HARD_CAP = 200
ID_HARD_CAP = 200
REF_HARD_CAP = 500
MAX_FINDINGS = 200
MAX_TARGETS = 50

# Typed upstream anchors a finding / target may carry (bounded ids only — never a body).
PROVENANCE_ANCHOR_FIELDS: tuple[str, ...] = (
    "workflow_id", "stage_id", "stage_item_id", "feedback_id", "recommendation_id", "draft_id",
    "draft_section_id", "packet_id", "projection_id", "projection_item_id", "context_pack_id",
    "review_item_id", "claim_id", "citation_id", "decision_id", "preference_id", "open_loop_id",
    "source_id", "source_ref", "source_root_key", "rel_path", "note_rel_path",
)


class QualityValidationError(ValueError):
    """Raised on a structural/enum/size problem building a quality run / finding / target row."""


def canonical_json(obj: Any) -> str:
    """Deterministic JSON (sorted keys) for policy/context digests folded into quality ids."""
    return json.dumps(obj or {}, sort_keys=True, separators=(",", ":"), default=str)


def _clean_id(value: Any, cap: int = ID_HARD_CAP) -> str | None:
    if value is None:
        return None
    text = bound_text(str(value).strip(), cap)
    return text or None


def _anchors(raw: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in PROVENANCE_ANCHOR_FIELDS:
        val = _clean_id(raw.get(name), REF_HARD_CAP)
        if val:
            out[name] = val
    return out


# --- payload dataclasses ----------------------------------------------------------------------------------
@dataclass
class QualityFinding:
    """One advisory quality observation. Advisory only — it may recommend operator review but never sets or
    mutates a review disposition."""

    finding_type: str
    severity: str = SEVERITY_WARN
    target_kind: str | None = None
    target_id: str | None = None
    detail: str | None = None
    advice: str | None = None
    anchors: dict[str, Any] = field(default_factory=dict)
    review_state: str | None = None
    effective_state: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized_anchors(self) -> dict[str, str]:
        return _anchors(self.anchors)

    def signature(self) -> str:
        anchors = ";".join(f"{k}={v}" for k, v in sorted(self.normalized_anchors().items()))
        return f"{self.finding_type}|{self.severity}|{self.target_kind or ''}|{self.target_id or ''}|{anchors}"

    def to_row(self, quality_run_id: str, order: int) -> dict[str, Any]:
        if self.finding_type not in QUALITY_FINDING_TYPES:
            raise QualityValidationError(f"unknown_finding_type:{self.finding_type}")
        if self.severity not in QUALITY_SEVERITIES:
            raise QualityValidationError(f"unknown_severity:{self.severity}")
        row: dict[str, Any] = {
            "finding_id": compute_finding_id(quality_run_id, self.finding_type, self.target_id, order),
            "quality_run_id": quality_run_id,
            "finding_order": int(order),
            "finding_type": self.finding_type,
            "severity": self.severity,
            "target_kind": self.target_kind or None,
            "target_id": _clean_id(self.target_id),
            "detail": bound_text(self.detail, DETAIL_HARD_CAP) or None,
            "advice": bound_text(self.advice, ADVICE_HARD_CAP) or None,
            # Pinned advisory / no-execution values (defense-in-depth alongside the schema CHECK).
            "action_policy": ACTION_POLICY,
            "execution_policy": EXECUTION_POLICY,
            "review_policy": REVIEW_POLICY,
            "requires_operator_review": 1,
            "review_state": self.review_state or None,
            "effective_state": self.effective_state or None,
            "finding_digest": sha256_hex(self.signature())[:24],
            "metadata_json": canonical_json(self.metadata) if self.metadata else None,
        }
        row.update(self.normalized_anchors())
        return row


@dataclass
class QualityTarget:
    """The evaluated target, with preserved provenance + copied review/effective state (metadata only)."""

    target_kind: str
    target_id: str
    target_label: str | None = None
    anchors: dict[str, Any] = field(default_factory=dict)
    target_digest: str | None = None
    review_state: str | None = None
    effective_state: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized_anchors(self) -> dict[str, str]:
        return _anchors(self.anchors)

    def to_row(self, quality_run_id: str, order: int) -> dict[str, Any]:
        if self.target_kind not in QUALITY_TARGET_KINDS:
            raise QualityValidationError(f"unknown_target_kind:{self.target_kind}")
        tid = _clean_id(self.target_id)
        if not tid:
            raise QualityValidationError("quality_target_requires_target_id")
        row: dict[str, Any] = {
            "quality_target_id": compute_quality_target_id(quality_run_id, self.target_kind, tid, order),
            "quality_run_id": quality_run_id,
            "target_order": int(order),
            "target_kind": self.target_kind,
            "target_id": tid,
            "target_label": bound_text(self.target_label, LABEL_HARD_CAP) or None,
            "target_digest": _clean_id(self.target_digest, REF_HARD_CAP),
            "review_state": self.review_state or None,
            "effective_state": self.effective_state or None,
            "metadata_json": canonical_json(self.metadata) if self.metadata else None,
        }
        row.update(self.normalized_anchors())
        return row


# --- deterministic identity -------------------------------------------------------------------------------
def compute_target_digest(target_kind: str, target_id: str, signals: list[str]) -> str:
    """Digest over the evaluated target's stable signals (ids/states/counts). A changed target changes this."""
    joined = "|".join(sorted(signals))
    return sha256_hex(f"{target_kind}|{target_id}|{joined}")[:24]


def compute_request_digest(target_kind: str, target_id: str, policy_json: str) -> str:
    """Lineage key: identical (target_kind, target_id, policy) → same request_digest → supersede lineage."""
    return sha256_hex(f"{target_kind}|{target_id}|{policy_json}")[:24]


def compute_input_digest(request_digest: str, target_digest: str) -> str:
    return sha256_hex(f"{request_digest}#{target_digest}#{QUALITY_EVALUATOR_VERSION}")[:24]


def compute_output_digest(finding_ids: list[str]) -> str:
    return sha256_hex("|".join(sorted(finding_ids)))[:24]


def compute_quality_run_id(target_kind: str, target_id: str, request_digest: str, input_digest: str) -> str:
    key = f"{target_kind}|{target_id}|{request_digest}|{input_digest}|{QUALITY_EVALUATOR_VERSION}"
    return sha256_hex(key)[:24]


def compute_finding_id(quality_run_id: str, finding_type: str, target_id: str | None, order: int) -> str:
    return sha256_hex(f"{quality_run_id}|{finding_type}|{target_id or ''}|{int(order)}")[:24]


def compute_quality_target_id(quality_run_id: str, target_kind: str, target_id: str, order: int) -> str:
    return sha256_hex(f"{quality_run_id}|{target_kind}|{target_id}|{int(order)}")[:24]


def compute_quality_receipt_id(quality_run_id: str, input_digest: str, output_digest: str) -> str:
    return sha256_hex(f"{quality_run_id}|{input_digest}|{output_digest}|{QUALITY_EVALUATOR_VERSION}")[:24]


def severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"risk": 0, "warn": 0, "info": 0}
    for f in findings:
        sev = f.get("severity")
        if sev in counts:
            counts[sev] += 1
    return counts
