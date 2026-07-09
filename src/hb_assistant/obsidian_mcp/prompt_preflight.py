"""Prompt Preflight — deterministic route engine (read-only, no content reads).

Given a raw prompt, classify intent → source-of-truth → candidate families → workflow recipe → specific
tools → authorization → retrieval budget → memory opportunity → fallback plan, and emit a single route plan
dict. This module performs NO writes, NO staging, NO promotion, and reads NO source content — it only reasons
over the static routing manifests (families / workflows / tool entries) plus optional live availability and
freshness signals. Organization-neutral.
"""

from __future__ import annotations

from typing import Any

from .tool_family_manifest import family_record
from .workflow_recipe_manifest import WORKFLOWS, workflow_record

# Source-of-truth label per family (§10). Where a generated file lives vs canonical memory vs indexed source
# files — so the caller never confuses a generated .md file with a vault note or a decision record.
_SOURCE_OF_TRUTH: dict[str, str] = {
    "client_output_workspace": "generated outputs workspace (outputs root; NOT the vault)",
    "output_receipts_manifests": "generated outputs receipts/manifest",
    "artifact_workspace": "staged artifact proposals (not yet canonical)",
    "canonical_promotion": "canonical memory (Obsidian cards)",
    "obsidian_materialization": "canonical memory (Obsidian cards)",
    "assistant_decision_memory": "canonical decision/preference/open-loop records",
    "assistant_source_connector": "indexed source files",
    "assistant_navigation": "indexed source files + generated cards",
    "assistant_context_packs": "durable context packs (source-backed)",
    "assistant_memory": "compiled memory (source-backed)",
    "assistant_research_packets": "research packets (citation-backed answer CONTEXT)",
    "assistant_answer_drafts": "citation-safe answer drafts (advisory)",
    "status_health": "server status (not content)",
    "tool_catalog_help_query": "tool catalog (not content)",
    "client_tool_manifest": "tool operating manifest",
    "prompt_routing": "routing manifests (advisory)",
}

# Write action classes that require explicit operator authorization before executing.
_WRITE_CLASSES = frozenset({"staged_write", "canonical_promotion", "archive"})

# Retrieval layers ordered from cheapest to most expensive.
_LAYER_ORDER = ("route_only", "metadata_discovery", "candidate_triage", "bounded_read", "deep_parse")

# Memory-opportunity trigger phrases (§18) — the operator states a durable fact worth capturing, but the
# preflight NEVER auto-stages; it only flags the opportunity.
_MEMORY_CUES = (
    "remember that", "remember this", "for the future", "going forward", "from now on",
    "we decided", "i decided", "the decision is", "our preference", "i prefer", "always ",
    "never ", "make a note", "keep in mind", "standing rule",
)


# Destructive-intent cues (§13). The engine had no destructive classifier, so "delete README.md from the
# vault" fell through to a benign unknown route. A destructive verb applied to a vault/file/record object
# is surfaced explicitly: never self-authorized, target confirmation required, reversible archive preferred.
_DESTRUCTIVE_VERBS = ("delete", "remove", "wipe", "destroy", "erase", "purge", "rm -")
_DESTRUCTIVE_OBJECTS = ("vault", "note", "file", "readme", "card", "record", "folder", "document",
                        "page", ".md", "artifact", "output")


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def _is_destructive(prompt_l: str) -> bool:
    """A destructive verb applied to a stored object (avoids firing on benign 'remove the filter')."""
    return (any(v in prompt_l for v in _DESTRUCTIVE_VERBS)
            and any(o in prompt_l for o in _DESTRUCTIVE_OBJECTS))


def _score_workflow(prompt_l: str, wf: dict[str, Any]) -> int:
    score = 0
    for phrase in wf["trigger_phrases"]:
        p = phrase.lower()
        if p and p in prompt_l:
            # weight multi-word phrases more than single tokens
            score += 2 if " " in p else 1
    return score


# Tie-break priority by intent when workflow scores are EQUAL: an operator who explicitly says
# "document/capture/create" must not lose to an incidental retrieval substring match. Previously the
# alphabetical workflow_id tie-break let (e.g.) canonical_open_loop_retrieval beat document_session for
# "document this session as decisions and open loops". Lower tier sorts first.
_INTENT_TIE_TIER: dict[str, int] = {
    "capture": 0, "documentation": 0, "staged_write": 1, "generation": 2, "canonical_promotion": 3,
}
_DEFAULT_INTENT_TIER = 5  # retrieval / discovery / status / routing


def _intent_tier(wf: dict[str, Any]) -> int:
    return min((_INTENT_TIE_TIER.get(ic, _DEFAULT_INTENT_TIER) for ic in wf["intent_classes"]),
               default=_DEFAULT_INTENT_TIER)


def _rank_workflows(prompt_l: str) -> list[tuple[int, dict[str, Any]]]:
    scored = [(_score_workflow(prompt_l, wf), wf) for wf in WORKFLOWS]
    scored = [(s, wf) for s, wf in scored if s > 0]
    # Rank by score, then by intent tier (capture/write before retrieval on a tie), then workflow_id.
    scored.sort(key=lambda t: (-t[0], _intent_tier(t[1]), t[1]["workflow_id"]))
    return scored


def _retrieval_budget(wf: dict[str, Any], has_exact_id: bool) -> dict[str, Any]:
    layer = wf["default_retrieval_layer"]
    # Broad/ambiguous retrieval must triage before deep reads; an exact id/filename may go bounded.
    if layer in ("metadata_discovery", "candidate_triage") and has_exact_id:
        recommended_next = "bounded_read"
    else:
        idx = _LAYER_ORDER.index(layer) if layer in _LAYER_ORDER else 0
        recommended_next = _LAYER_ORDER[min(idx + 1, len(_LAYER_ORDER) - 1)]
    return {
        "default_layer": layer,
        "recommended_next_layer": recommended_next,
        "max_candidates": wf["max_default_candidates"],
        "max_chars": wf["max_default_chars"],
        "deep_parse_requires_operator_selection": True,
        "why_not_deep_read_all": (
            "Deep-reading every candidate is unbounded and unsafe; triage metadata first, then read only "
            "the operator-selected item within the char budget."
        ),
    }


def _authorization(wf: dict[str, Any], confident: bool) -> dict[str, Any]:
    action_class = wf["operator_authorization_policy"]
    is_write = action_class in _WRITE_CLASSES
    return {
        "action_class": action_class,
        "write_risk": wf["write_risk"],
        # The prompt never itself authorizes execution of a write/promotion/archive — those need an explicit
        # operator go + server-minted approval. Reads are self-authorizing.
        "prompt_authorizes_execution": (not is_write),
        "additional_approval_required": bool(is_write) or bool(wf["additional_approval_points"]),
        "approval_points": list(wf["additional_approval_points"]),
        "requires_explicit_operator_go": bool(is_write) and not confident,
    }


def _memory_opportunity(prompt_l: str, primary_family: str) -> dict[str, Any]:
    hit = next((cue.strip() for cue in _MEMORY_CUES if cue in prompt_l), None)
    detected = hit is not None and primary_family not in ("artifact_workspace", "canonical_promotion")
    return {
        "detected": detected,
        "cue": hit,
        "suggested_workflow": "document_session" if detected else None,
        "note": (
            "The prompt states a durable fact/preference. Offer to capture it via the artifact workspace "
            "(document_session) — but only stage after explicit operator confirmation."
        ) if detected else "",
        "must_not_auto_stage": True,
    }


def _fallback_plan(wf: dict[str, Any], is_write: bool) -> dict[str, Any]:
    return {
        "rules": list(wf["fallback_rules"]),
        # Controlled writes must never silently fall back to a low-level/legacy writer.
        "unsafe_fallback_blocked": is_write,
        "failure_recovery": wf["failure_recovery"],
    }


def route_prompt(
    prompt: str,
    *,
    available_tools: frozenset[str] | set[str] | None = None,
    has_exact_id: bool = False,
    freshness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a read-only route plan for ``prompt`` (full §4 schema). Never writes or reads content."""
    prompt_l = _norm(prompt)

    # Destructive intent takes precedence: a delete/remove/wipe of a stored object is never
    # self-authorized and must not be silently classified as a benign unknown.
    if _is_destructive(prompt_l):
        return _destructive_route(prompt, prompt_l, freshness)

    # Secret extraction / arbitrary path write refusals (deterministic, fail closed).
    if any(c in prompt_l for c in ("show me secrets", "show tokens", "dump credentials", "api keys",
                                   "extract password")):
        return _safety_refusal_route(
            prompt, prompt_l, freshness,
            intent="secret_extraction_refusal",
            rationale="Refuse secret/token extraction.",
        )
    if any(c in prompt_l for c in ("write a file to /tmp", "write to /tmp", "/tmp/anything",
                                   "save to /etc/")):
        return _safety_refusal_route(
            prompt, prompt_l, freshness,
            intent="arbitrary_path_write_refusal",
            rationale="Refuse arbitrary host path writes; use generated-output workspace only.",
        )

    ranked = _rank_workflows(prompt_l)

    if not ranked:
        # Unknown intent → clarify, do not guess a write.
        return _unknown_route(prompt, prompt_l, freshness)

    best_score, best_wf = ranked[0]
    # Candidate families: families of workflows within 1 point of the best (ambiguity band).
    candidate_families: list[str] = []
    alt_workflows: list[str] = []
    for s, wf in ranked:
        if s >= best_score - 1:
            if wf["family_id"] not in candidate_families:
                candidate_families.append(wf["family_id"])
            if wf["workflow_id"] != best_wf["workflow_id"]:
                alt_workflows.append(wf["workflow_id"])

    primary_family = best_wf["family_id"]
    runner_up = ranked[1][0] if len(ranked) > 1 else 0
    # Confidence: strong single match, or clear margin.
    if best_score >= 3 or (best_score >= 2 and best_score - runner_up >= 2):
        confidence = "high"
    elif best_score >= 2 or (best_score == 1 and len(candidate_families) == 1):
        confidence = "medium"
    else:
        confidence = "low"
    confident = confidence in ("high", "medium")

    # Tool selection: workflow tool_sequence filtered by live availability.
    seq = list(best_wf["tool_sequence"])
    if available_tools is not None:
        unavailable = [t for t in seq if t not in available_tools]
        recommended_tools = [t for t in seq if t in available_tools]
    else:
        unavailable = []
        recommended_tools = seq
    workflow_available = not unavailable

    action_class = best_wf["operator_authorization_policy"]
    is_write = action_class in _WRITE_CLASSES
    authorization = _authorization(best_wf, confident)
    fam = family_record(primary_family) or {}

    plan: dict[str, Any] = {
        "prompt": prompt,
        "intent": {
            "primary_class": best_wf["intent_classes"][0] if best_wf["intent_classes"] else "unknown",
            "classes": list(best_wf["intent_classes"]),
        },
        "source_of_truth": _SOURCE_OF_TRUTH.get(primary_family, "unclassified"),
        "candidate_families": candidate_families,
        "primary_family": primary_family,
        "recommended_workflow": best_wf["workflow_id"],
        "alternative_workflows": alt_workflows,
        "recommended_tools": recommended_tools,
        "workflow_available": workflow_available,
        "unavailable_tools": unavailable,
        "authorization": authorization,
        "retrieval_budget": _retrieval_budget(best_wf, has_exact_id),
        "provenance_required": list(best_wf["required_provenance"]),
        "memory_opportunity": _memory_opportunity(prompt_l, primary_family),
        "must_not_use": list(best_wf["must_not_use"]) + list(fam.get("family_level_negative_instructions", [])),
        "fallback_plan": _fallback_plan(best_wf, is_write),
        "route_confidence": confidence,
        "routing_rationale": (
            f"Matched workflow '{best_wf['workflow_id']}' (score {best_score}) in family '{primary_family}'; "
            f"source of truth = {_SOURCE_OF_TRUTH.get(primary_family, 'unclassified')}."
        ),
        "clarifying_question": None,
        "preflight_is_read_only": True,
    }

    # Low confidence + a write/promotion/archive → do not act; ask first.
    if not confident and is_write:
        plan["clarifying_question"] = (
            f"This looks like a '{action_class}' action but intent is ambiguous. Confirm the target "
            f"(e.g. generated file vs canonical memory) before I stage anything."
        )
        plan["recommended_tools"] = []
        plan["recommended_workflow"] = "context_preflight"

    plan["freshness"] = _freshness_view(freshness, is_write)
    return plan


def _unknown_route(prompt: str, prompt_l: str, freshness: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "intent": {"primary_class": "unknown", "classes": ["unknown"]},
        "source_of_truth": "unclassified",
        "candidate_families": ["prompt_routing"],
        "primary_family": "prompt_routing",
        "recommended_workflow": "context_preflight",
        "alternative_workflows": [],
        "recommended_tools": [],
        "workflow_available": True,
        "unavailable_tools": [],
        "authorization": {
            "action_class": "read", "write_risk": "none", "prompt_authorizes_execution": False,
            "additional_approval_required": False, "approval_points": [],
            "requires_explicit_operator_go": False,
        },
        "retrieval_budget": {
            "default_layer": "route_only", "recommended_next_layer": "metadata_discovery",
            "max_candidates": 10, "max_chars": 4000, "deep_parse_requires_operator_selection": True,
            "why_not_deep_read_all": "Intent is unclear; clarify before spending retrieval budget.",
        },
        "provenance_required": [],
        "memory_opportunity": _memory_opportunity(prompt_l, "prompt_routing"),
        "must_not_use": ["guessing a write/promotion target"],
        "fallback_plan": {"rules": [], "unsafe_fallback_blocked": True, "failure_recovery": ""},
        "route_confidence": "low",
        "routing_rationale": "No workflow trigger matched; route to a clarifying preflight.",
        "clarifying_question": "I couldn't confidently classify this request. What outcome do you want "
                               "(retrieve, generate a file, capture to memory, or promote)?",
        "preflight_is_read_only": True,
        "freshness": _freshness_view(freshness, is_write=False),
    }



def _safety_refusal_route(prompt: str, prompt_l: str, freshness: dict[str, Any] | None, *,
                          intent: str, rationale: str) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "intent": {"primary_class": intent, "classes": [intent, "refusal"]},
        "source_of_truth": "unclassified",
        "candidate_families": ["prompt_routing"],
        "primary_family": "prompt_routing",
        "recommended_workflow": "context_preflight",
        "alternative_workflows": [],
        "recommended_tools": [],
        "workflow_available": True,
        "unavailable_tools": [],
        "authorization": {
            "action_class": "read", "write_risk": "none", "prompt_authorizes_execution": False,
            "additional_approval_required": True, "approval_points": ["refusal — do not execute"],
            "requires_explicit_operator_go": True,
        },
        "retrieval_budget": {
            "default_layer": "route_only", "recommended_next_layer": "route_only",
            "max_candidates": 0, "max_chars": 0, "deep_parse_requires_operator_selection": True,
            "why_not_deep_read_all": rationale,
        },
        "provenance_required": [],
        "memory_opportunity": _memory_opportunity(prompt_l, "prompt_routing"),
        "must_not_use": [rationale, "any write or extract tool for this intent"],
        "fallback_plan": {"rules": ["refuse"], "unsafe_fallback_blocked": True, "failure_recovery": ""},
        "route_confidence": "high",
        "routing_rationale": rationale,
        "clarifying_question": rationale,
        "preflight_is_read_only": True,
        "freshness": _freshness_view(freshness, is_write=False),
        "refused": True,
    }


def _destructive_route(prompt: str, prompt_l: str, freshness: dict[str, Any] | None) -> dict[str, Any]:
    """Route for a detected destructive request: flag it high-risk, never self-authorize, prefer a
    reversible archive plan, and require explicit operator confirmation of the exact target."""
    return {
        "prompt": prompt,
        "intent": {"primary_class": "destructive", "classes": ["destructive"]},
        "source_of_truth": "unclassified",
        "candidate_families": ["prompt_routing"],
        "primary_family": "prompt_routing",
        "recommended_workflow": "context_preflight",
        "alternative_workflows": [],
        "recommended_tools": [],  # never auto-select a destructive tool
        "workflow_available": True,
        "unavailable_tools": [],
        "authorization": {
            "action_class": "destructive", "write_risk": "high",
            "prompt_authorizes_execution": False, "additional_approval_required": True,
            "approval_points": ["explicit operator confirmation of the exact target + irreversibility"],
            "requires_explicit_operator_go": True,
        },
        "retrieval_budget": {
            "default_layer": "route_only", "recommended_next_layer": "route_only",
            "max_candidates": 0, "max_chars": 0, "deep_parse_requires_operator_selection": True,
            "why_not_deep_read_all": "Destructive intent — do not spend retrieval budget; confirm first.",
        },
        "provenance_required": [],
        "memory_opportunity": _memory_opportunity(prompt_l, "prompt_routing"),
        "must_not_use": ["executing an irreversible delete", "guessing a delete/remove target",
                         "any low-level or bulk delete tool"],
        "fallback_plan": {"rules": ["prefer a reversible archive/plan over a delete"],
                          "unsafe_fallback_blocked": True, "failure_recovery": ""},
        "route_confidence": "high",
        "routing_rationale": ("Destructive intent detected (delete/remove/wipe/destroy of a stored "
                              "object). Destructive execution is not self-authorized; confirm the exact "
                              "target and prefer a reversible archive plan."),
        "clarifying_question": ("This looks like a destructive request. Deletes are not executed from a "
                                "prompt — confirm the exact target, and note that a reversible archive "
                                "(vault_archive_note_plan / vault_delete_note_plan, which substitutes "
                                "archive) is preferred over an irreversible delete. Proceed?"),
        "preflight_is_read_only": True,
        "destructive_intent": True,
        "freshness": _freshness_view(freshness, is_write=True),
    }


def _freshness_view(freshness: dict[str, Any] | None, is_write: bool) -> dict[str, Any]:
    if not freshness:
        return {"checked": False, "stale": False, "staleness_state": "unknown",
                "warnings": [], "write_blocked_by_staleness": False}
    stale = bool(freshness.get("stale"))
    return {
        "checked": True,
        "stale": stale,
        "staleness_state": freshness.get("staleness_state", "unknown"),
        "warnings": list(freshness.get("warnings", [])),
        # Reads proceed with a warning; writes/promotion/archive fail closed on a stale surface.
        "write_blocked_by_staleness": bool(stale and is_write),
    }


def explain_route(prompt: str, **kwargs: Any) -> dict[str, Any]:
    """Route + attach the full workflow/family records behind the decision (for pa_prompt_route_explain)."""
    plan = route_prompt(prompt, **kwargs)
    wf = workflow_record(plan["recommended_workflow"])
    plan["workflow_detail"] = wf
    plan["family_detail"] = family_record(plan["primary_family"])
    return plan
