"""Models, enums, deterministic identity, and bounded caps for the N8C-15 workflow contract/routing layer.

Neutral and deterministic (no DB, no vault, no model, NO LLM, no network). This module defines the
canonical workflow-type and routing-target vocabularies, the bounded ``WorkflowRequest`` inputs, the fixed
no-execution policy constants, and a conservative keyword classifier. It NEVER executes an action, stages a
draft, schedules a job, generates a final answer, or persists anything.

A workflow ``workflow_id`` is an EPHEMERAL deterministic response identifier folded from the router version
plus a digest of the bounded request — it is NOT a durable run record and is never written to the database
(N8C-15 adds no schema and no workflow-run tables). Determinism only makes identical requests reproducible.

The router built on these models is ROUTE-ONLY: it reads existing N8C artifacts through their read
repositories and returns a normalized envelope of BOUNDED, whitelisted metadata (ids, types, status,
already-bounded titles/summaries, citation ids, review labels, source refs, counts, warnings, deferred
markers). It never copies a full packet/draft/pack export, a raw source/card/vault body, a raw email body,
a raw prompt/response, or a full upstream payload.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .memory_models import bound_text, sha256_hex

# Bump when the routing/serialization contract changes — folded into the ephemeral workflow_id.
WORKFLOW_ROUTER_VERSION = "workflow-router-v1"

# --- canonical workflow types -----------------------------------------------------------
WF_ASK_SECOND_BRAIN = "ask_second_brain"
WF_RESEARCH_ANSWER = "research_answer"
WF_SOURCE_FILE_LOOKUP = "source_file_lookup"
WF_MEETING_PREP = "meeting_prep"
WF_DAILY_BRIEF_CONTEXT = "daily_brief_context"
WF_PROJECT_INTELLIGENCE_CONTEXT = "project_intelligence_context"
WF_OPEN_LOOP_TRIAGE = "open_loop_triage"
WF_DECISION_PREFERENCE_LOOKUP = "decision_preference_lookup"
WF_DRAFT_REVIEW = "draft_review"
WF_ACTION_DRAFT_PREPARATION = "action_draft_preparation"
WF_UNKNOWN = "unknown"

WORKFLOW_TYPES = frozenset({
    WF_ASK_SECOND_BRAIN, WF_RESEARCH_ANSWER, WF_SOURCE_FILE_LOOKUP, WF_MEETING_PREP,
    WF_DAILY_BRIEF_CONTEXT, WF_PROJECT_INTELLIGENCE_CONTEXT, WF_OPEN_LOOP_TRIAGE,
    WF_DECISION_PREFERENCE_LOOKUP, WF_DRAFT_REVIEW, WF_ACTION_DRAFT_PREPARATION, WF_UNKNOWN,
})

# --- canonical routing targets (existing N8C read surfaces) -----------------------------
TARGET_SOURCE_CONNECTOR = "source_connector"
TARGET_RESEARCH_PACKETS = "research_packets"
TARGET_ANSWER_DRAFTS = "answer_drafts"
TARGET_INTELLIGENCE_PROJECTIONS = "intelligence_projections"
TARGET_REVIEW_QUEUE = "review_queue"
TARGET_DECISION_MEMORY = "decision_memory"
TARGET_MEMORY = "memory"
TARGET_CONTEXT_PACKS = "context_packs"
TARGET_CLAIMS = "claims"
TARGET_OPEN_LOOPS = "open_loops"
TARGET_UNKNOWN = "unknown"

ROUTING_TARGETS = frozenset({
    TARGET_SOURCE_CONNECTOR, TARGET_RESEARCH_PACKETS, TARGET_ANSWER_DRAFTS,
    TARGET_INTELLIGENCE_PROJECTIONS, TARGET_REVIEW_QUEUE, TARGET_DECISION_MEMORY, TARGET_MEMORY,
    TARGET_CONTEXT_PACKS, TARGET_CLAIMS, TARGET_OPEN_LOOPS, TARGET_UNKNOWN,
})

# --- workflow result statuses -----------------------------------------------------------
STATUS_ROUTED = "routed"
STATUS_NEEDS_CLARIFICATION = "needs_clarification"
STATUS_INSUFFICIENT_CONTEXT = "insufficient_context"
STATUS_MISSING_REQUIRED_ARTIFACT = "missing_required_artifact"
STATUS_DEFERRED = "deferred"

WORKFLOW_STATUSES = frozenset({
    STATUS_ROUTED, STATUS_NEEDS_CLARIFICATION, STATUS_INSUFFICIENT_CONTEXT,
    STATUS_MISSING_REQUIRED_ARTIFACT, STATUS_DEFERRED,
})

# --- fixed policy constants (never overridable) -----------------------------------------
# No workflow result may imply that an action was executed, scheduled, or that a record was written.
ACTION_POLICY = "no_execution"
EXECUTION_POLICY = "route_only"
REVIEW_POLICY = "preserve_review_state"
CITATION_POLICY = "preserve_citations"
SOURCE_POLICY = "use_existing_artifacts_only"

POLICY_BLOCK = {
    "action_policy": ACTION_POLICY,
    "execution_policy": EXECUTION_POLICY,
    "review_policy": REVIEW_POLICY,
    "citation_policy": CITATION_POLICY,
    "source_policy": SOURCE_POLICY,
}

# --- hard caps (keep every envelope bounded) --------------------------------------------
QUERY_HARD_CAP = 1_000
OBJECTIVE_HARD_CAP = 1_000
TEXT_FIELD_CAP = 500
ID_HARD_CAP = 200
LABEL_HARD_CAP = 200
MAX_SELECTED_ARTIFACTS = 50
MAX_ITEMS = 100
MAX_CITATIONS = 200
MAX_SOURCE_REFS = 100
MAX_REVIEW_LABELS = 50
MAX_OPEN_QUESTIONS = 100
MAX_NEXT_STEPS = 25
MAX_WARNINGS = 50
MAX_DEFERRED = 25
_MAX_META_VALUE_CAP = 300


class WorkflowValidationError(ValueError):
    """Raised on a structural problem building a workflow request (rare — inputs are bounded, not rejected)."""


def canonical_json(obj: Any) -> str:
    """Deterministic JSON (sorted keys) for the request digest folded into the workflow_id."""
    return json.dumps(obj or {}, sort_keys=True, separators=(",", ":"), default=str)


def _clean_id(value: Any) -> str | None:
    """Bound an artifact-id input; empty/blank → None."""
    if value is None:
        return None
    text = bound_text(str(value).strip(), ID_HARD_CAP)
    return text or None


# Fields that carry an explicit artifact id, in router-preference order per workflow type.
ARTIFACT_ID_FIELDS = (
    "draft_id", "packet_id", "projection_id", "context_pack_id", "review_item_id",
    "memory_node_id", "decision_id", "preference_id", "open_loop_id",
)


@dataclass
class WorkflowRequest:
    """A bounded, deterministic workflow request. All text is capped; ids are trimmed to bounded strings."""

    workflow_type: str | None = None
    query: str | None = None
    objective: str | None = None
    domain: str | None = None
    project_key: str | None = None
    source_root_key: str | None = None
    draft_id: str | None = None
    packet_id: str | None = None
    projection_id: str | None = None
    context_pack_id: str | None = None
    review_item_id: str | None = None
    memory_node_id: str | None = None
    decision_id: str | None = None
    preference_id: str | None = None
    open_loop_id: str | None = None
    requested_by: str = "system"

    @classmethod
    def from_inputs(cls, **kwargs: Any) -> WorkflowRequest:
        """Build a bounded request from raw inputs. Never raises on an unknown workflow_type — the router
        maps that to needs_clarification. Text fields are hard-capped; ids trimmed."""
        wf = kwargs.get("workflow_type")
        wf = bound_text(str(wf).strip(), ID_HARD_CAP) if wf else None
        return cls(
            workflow_type=wf or None,
            query=bound_text(kwargs.get("query"), QUERY_HARD_CAP) or None,
            objective=bound_text(kwargs.get("objective"), OBJECTIVE_HARD_CAP) or None,
            domain=bound_text(kwargs.get("domain"), TEXT_FIELD_CAP) or None,
            project_key=bound_text(kwargs.get("project_key"), TEXT_FIELD_CAP) or None,
            source_root_key=bound_text(kwargs.get("source_root_key"), TEXT_FIELD_CAP) or None,
            draft_id=_clean_id(kwargs.get("draft_id")),
            packet_id=_clean_id(kwargs.get("packet_id")),
            projection_id=_clean_id(kwargs.get("projection_id")),
            context_pack_id=_clean_id(kwargs.get("context_pack_id")),
            review_item_id=_clean_id(kwargs.get("review_item_id")),
            memory_node_id=_clean_id(kwargs.get("memory_node_id")),
            decision_id=_clean_id(kwargs.get("decision_id")),
            preference_id=_clean_id(kwargs.get("preference_id")),
            open_loop_id=_clean_id(kwargs.get("open_loop_id")),
            requested_by=bound_text(kwargs.get("requested_by") or "system", ID_HARD_CAP) or "system",
        )

    def artifact_ids(self) -> dict[str, str]:
        """The subset of artifact-id fields that were supplied (bounded)."""
        out: dict[str, str] = {}
        for name in ARTIFACT_ID_FIELDS:
            val = getattr(self, name)
            if val:
                out[name] = val
        return out

    def to_public_dict(self) -> dict[str, Any]:
        """Bounded echo of the request for the response envelope (no unbounded fields exist here)."""
        d = {
            "workflow_type": self.workflow_type,
            "query": self.query,
            "objective": self.objective,
            "domain": self.domain,
            "project_key": self.project_key,
            "source_root_key": self.source_root_key,
            "requested_by": self.requested_by,
        }
        d.update(self.artifact_ids())
        return {k: v for k, v in d.items() if v is not None}


def compute_workflow_id(workflow_type: str, request: WorkflowRequest) -> str:
    """Deterministic, EPHEMERAL response id (never persisted). Same inputs → same id."""
    digest = sha256_hex(canonical_json(request.to_public_dict()))[:24]
    return sha256_hex(f"{WORKFLOW_ROUTER_VERSION}|{workflow_type}|{digest}")[:24]


# --- conservative keyword classification ------------------------------------------------
# Each category maps to a tuple of lowercase keyword tokens. Classification is deterministic and
# conservative: a category "hits" if ANY of its tokens is a substring of the combined query+objective.
# Ambiguity (zero categories, or MORE THAN ONE category) resolves to WF_UNKNOWN — the router then returns
# needs_clarification / insufficient_context rather than guessing (clarification #9). "answer/packet/draft"
# hints map to draft_review (a read/inspect flow), never to a generative answer.
_KEYWORD_CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (WF_SOURCE_FILE_LOOKUP, ("file", "folder", "pdf", "contract", "drawing", "invoice", "proposal")),
    (WF_MEETING_PREP, ("meeting", "agenda", "attendee", "prep")),
    (WF_DAILY_BRIEF_CONTEXT, ("daily brief", "today", "overnight")),
    (WF_PROJECT_INTELLIGENCE_CONTEXT,
     ("project", "risk", "rfi", "submittal", "change order", "forecast")),
    (WF_OPEN_LOOP_TRIAGE, ("open loop", "follow up", "follow-up", "waiting for", "waiting on")),
    (WF_DECISION_PREFERENCE_LOOKUP, ("decision", "decided", "preference", "prefer")),
    (WF_DRAFT_REVIEW, ("draft", "citation", "packet")),
)


def classify_workflow_type_from_keywords(query: str | None, objective: str | None) -> str:
    """Conservative single-category keyword classifier. Returns a workflow type or WF_UNKNOWN.

    Returns a concrete type ONLY when exactly ONE category matches. Zero matches or MULTIPLE conflicting
    categories → WF_UNKNOWN (the router turns that into needs_clarification / insufficient_context)."""
    haystack = f"{query or ''} {objective or ''}".lower()
    if not haystack.strip():
        return WF_UNKNOWN
    hits = [wf for wf, tokens in _KEYWORD_CATEGORIES if any(tok in haystack for tok in tokens)]
    return hits[0] if len(hits) == 1 else WF_UNKNOWN


@dataclass
class RoutingDecision:
    """The deterministic routing outcome: chosen targets + why, and how the workflow type was resolved."""

    workflow_type: str
    resolution: str  # "explicit" | "keyword_fallback" | "unresolved"
    primary_target: str
    targets: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_type": self.workflow_type,
            "resolution": self.resolution,
            "primary_target": self.primary_target,
            "targets": list(self.targets),
            "reason": bound_text(self.reason, TEXT_FIELD_CAP),
        }


def bound_meta_value(value: Any) -> Any:
    """Whitelist-safe scalar bound: strings capped, numbers/bools kept, dict/list/None dropped."""
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return bound_text(value, _MAX_META_VALUE_CAP)
    return None


def bounded_metadata(record: dict[str, Any], whitelist: tuple[str, ...]) -> dict[str, Any]:
    """Copy only whitelisted, bounded SCALAR fields from an upstream record. Never copies ``*_json`` blobs,
    ``metadata_json``, raw bodies, or nested payloads — any key ending in ``_json`` is skipped even if it
    appears in the whitelist (defense-in-depth for the bounded-metadata rule, clarification #8)."""
    out: dict[str, Any] = {}
    for key in whitelist:
        if key.endswith("_json") or key not in record:
            continue
        bounded = bound_meta_value(record[key])
        if bounded is not None:
            out[key] = bounded
    return out
