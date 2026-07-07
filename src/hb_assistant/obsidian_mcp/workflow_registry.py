"""Canonical N8C-15 workflow registry: the catalog of workflow types, their preferred routing targets over
existing N8C read surfaces, and their deferred-capability markers.

Pure/deterministic (no DB, no LLM, no I/O). The registry is the single source of truth for WHICH existing
artifact surfaces a workflow request may consult and WHAT is intentionally deferred to a later phase:
  * ``action_draft_preparation`` is CONTRACT-ONLY in N8C-15 — it stages nothing; action staging is N8C-18.
  * ``meeting_prep`` / ``daily_brief_context`` / ``project_intelligence_context`` / ``open_loop_triage``
    route to targets but their full workflow IMPLEMENTATION is deferred to N8C-17.
  * Live remote (MCP/ChatGPT) workflow consumption is deferred to N8C-16 — N8C-15 adds no MCP tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .workflow_models import (
    ROUTING_TARGETS,
    TARGET_ANSWER_DRAFTS,
    TARGET_CONTEXT_PACKS,
    TARGET_DECISION_MEMORY,
    TARGET_INTELLIGENCE_PROJECTIONS,
    TARGET_MEMORY,
    TARGET_OPEN_LOOPS,
    TARGET_RESEARCH_PACKETS,
    TARGET_REVIEW_QUEUE,
    TARGET_SOURCE_CONNECTOR,
    WF_ACTION_DRAFT_PREPARATION,
    WF_ASK_SECOND_BRAIN,
    WF_DAILY_BRIEF_CONTEXT,
    WF_DECISION_PREFERENCE_LOOKUP,
    WF_DRAFT_REVIEW,
    WF_MEETING_PREP,
    WF_OPEN_LOOP_TRIAGE,
    WF_PROJECT_INTELLIGENCE_CONTEXT,
    WF_RESEARCH_ANSWER,
    WF_SOURCE_FILE_LOOKUP,
    WF_UNKNOWN,
    WORKFLOW_ROUTER_VERSION,
    WORKFLOW_TYPES,
)


@dataclass(frozen=True)
class WorkflowSpec:
    """The routing contract for one canonical workflow type."""

    workflow_type: str
    summary: str
    primary_targets: tuple[str, ...]
    fallback_targets: tuple[str, ...] = ()
    # Artifact-id request fields that steer routing (checked in this order), if any.
    id_fields: tuple[str, ...] = ()
    # Capabilities intentionally NOT provided in N8C-15 (advisory markers only — never executed here).
    deferred_capabilities: tuple[str, ...] = ()
    # Phase that will carry the full implementation, if this phase only routes.
    implementation_deferred_to: str | None = None
    # True when the workflow is contract-only in N8C-15 (routes to nothing live; returns deferred).
    contract_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_type": self.workflow_type,
            "summary": self.summary,
            "primary_targets": list(self.primary_targets),
            "fallback_targets": list(self.fallback_targets),
            "id_fields": list(self.id_fields),
            "deferred_capabilities": list(self.deferred_capabilities),
            "implementation_deferred_to": self.implementation_deferred_to,
            "contract_only": self.contract_only,
        }


WORKFLOW_REGISTRY: dict[str, WorkflowSpec] = {
    WF_ASK_SECOND_BRAIN: WorkflowSpec(
        workflow_type=WF_ASK_SECOND_BRAIN,
        summary="Answer-context lookup preferring an existing answer draft, then research packet, then "
                "projection, then memory/decision/source surfaces. No final answer is generated.",
        primary_targets=(TARGET_ANSWER_DRAFTS, TARGET_RESEARCH_PACKETS, TARGET_INTELLIGENCE_PROJECTIONS),
        fallback_targets=(TARGET_MEMORY, TARGET_DECISION_MEMORY, TARGET_SOURCE_CONNECTOR),
        id_fields=("draft_id", "packet_id", "projection_id"),
    ),
    WF_RESEARCH_ANSWER: WorkflowSpec(
        workflow_type=WF_RESEARCH_ANSWER,
        summary="Citation-preserving answer-context over an existing answer draft or research packet. "
                "Requires a draft_id or packet_id; no final answer is generated.",
        primary_targets=(TARGET_ANSWER_DRAFTS, TARGET_RESEARCH_PACKETS),
        id_fields=("draft_id", "packet_id"),
    ),
    WF_SOURCE_FILE_LOOKUP: WorkflowSpec(
        workflow_type=WF_SOURCE_FILE_LOOKUP,
        summary="Route a source-file request to the indexed source-connector search/list/metadata surface. "
                "No live filesystem read, no scan/reindex, no source-card generation in the routing layer.",
        primary_targets=(TARGET_SOURCE_CONNECTOR,),
    ),
    WF_MEETING_PREP: WorkflowSpec(
        workflow_type=WF_MEETING_PREP,
        summary="Route to supplied context packs / projections / packets / drafts. Full workflow "
                "implementation deferred to N8C-17; no calendar or email side effects.",
        primary_targets=(TARGET_CONTEXT_PACKS, TARGET_INTELLIGENCE_PROJECTIONS,
                         TARGET_RESEARCH_PACKETS, TARGET_ANSWER_DRAFTS),
        id_fields=("context_pack_id", "projection_id", "packet_id", "draft_id"),
        deferred_capabilities=("build_meeting_prep_context",),
        implementation_deferred_to="N8C-17",
    ),
    WF_DAILY_BRIEF_CONTEXT: WorkflowSpec(
        workflow_type=WF_DAILY_BRIEF_CONTEXT,
        summary="Route to existing brief/context-pack artifacts if present. Full workflow implementation "
                "deferred to N8C-17.",
        primary_targets=(TARGET_CONTEXT_PACKS,),
        fallback_targets=(TARGET_INTELLIGENCE_PROJECTIONS,),
        id_fields=("context_pack_id",),
        deferred_capabilities=("build_daily_brief_context",),
        implementation_deferred_to="N8C-17",
    ),
    WF_PROJECT_INTELLIGENCE_CONTEXT: WorkflowSpec(
        workflow_type=WF_PROJECT_INTELLIGENCE_CONTEXT,
        summary="Route to source connector + memory + decision memory + projections where scoped. Full "
                "workflow implementation deferred to N8C-17.",
        primary_targets=(TARGET_INTELLIGENCE_PROJECTIONS, TARGET_MEMORY, TARGET_DECISION_MEMORY,
                         TARGET_SOURCE_CONNECTOR),
        id_fields=("projection_id", "memory_node_id"),
        deferred_capabilities=("build_project_intelligence_context",),
        implementation_deferred_to="N8C-17",
    ),
    WF_OPEN_LOOP_TRIAGE: WorkflowSpec(
        workflow_type=WF_OPEN_LOOP_TRIAGE,
        summary="Route to open-loop records + review/effective state. No task/reminder creation. Full "
                "workflow implementation deferred to N8C-17.",
        primary_targets=(TARGET_OPEN_LOOPS, TARGET_REVIEW_QUEUE),
        id_fields=("open_loop_id", "review_item_id"),
        deferred_capabilities=("build_open_loop_triage",),
        implementation_deferred_to="N8C-17",
    ),
    WF_DECISION_PREFERENCE_LOOKUP: WorkflowSpec(
        workflow_type=WF_DECISION_PREFERENCE_LOOKUP,
        summary="Route to decision/preference records + review/effective state.",
        primary_targets=(TARGET_DECISION_MEMORY,),
        fallback_targets=(TARGET_REVIEW_QUEUE,),
        id_fields=("decision_id", "preference_id"),
    ),
    WF_DRAFT_REVIEW: WorkflowSpec(
        workflow_type=WF_DRAFT_REVIEW,
        summary="Inspect an answer draft and/or research packet, reporting missing citations, candidate "
                "labels, and excluded-content warnings while preserving citation/review labels.",
        primary_targets=(TARGET_ANSWER_DRAFTS, TARGET_RESEARCH_PACKETS),
        id_fields=("draft_id", "packet_id"),
    ),
    WF_ACTION_DRAFT_PREPARATION: WorkflowSpec(
        workflow_type=WF_ACTION_DRAFT_PREPARATION,
        summary="Contract-only in N8C-15. Returns deferred capabilities only — no action, email draft, "
                "agenda, task, reminder, calendar item, or staged action object is created. Action "
                "staging is deferred to N8C-18.",
        primary_targets=(),
        deferred_capabilities=("stage_action_draft", "prepare_action_object"),
        implementation_deferred_to="N8C-18",
        contract_only=True,
    ),
    WF_UNKNOWN: WorkflowSpec(
        workflow_type=WF_UNKNOWN,
        summary="Unrecognized or ambiguous request. The router returns needs_clarification / "
                "insufficient_context rather than guessing.",
        primary_targets=(),
    ),
}

# Global note surfaced in the catalog: remote/live workflow consumption is a later phase.
LIVE_CONSUMPTION_DEFERRED_TO = "N8C-16"


def get_spec(workflow_type: str | None) -> WorkflowSpec | None:
    """Return the spec for a canonical workflow type, or None if unknown/invalid."""
    if not workflow_type:
        return None
    return WORKFLOW_REGISTRY.get(workflow_type)


def catalog() -> dict[str, Any]:
    """Serializable registry catalog: workflow specs + the routing-target vocabulary + fixed deferral notes.

    Read-only and side-effect-free — safe to expose over CLI/GET without touching the database."""
    return {
        "router_version": WORKFLOW_ROUTER_VERSION,
        "workflow_types": sorted(WORKFLOW_TYPES),
        "routing_targets": sorted(ROUTING_TARGETS),
        "workflows": [WORKFLOW_REGISTRY[wf].to_dict() for wf in sorted(WORKFLOW_REGISTRY)],
        "live_consumption_deferred_to": LIVE_CONSUMPTION_DEFERRED_TO,
        "notes": {
            "action_staging_deferred_to": "N8C-18",
            "full_workflow_implementation_deferred_to": "N8C-17",
            "operator_ui_deferred_to": "N8C-13",
        },
    }
