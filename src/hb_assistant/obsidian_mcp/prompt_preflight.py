"""Prompt Preflight — deterministic route engine (read-only, no content reads).

Given a raw prompt, classify intent → source-of-truth → candidate families → workflow recipe → specific
tools → authorization → retrieval budget → memory opportunity → fallback plan, and emit a single route plan
dict. This module performs NO writes, NO staging, NO promotion, and reads NO source content — it only reasons
over the static routing manifests (families / workflows / tool entries) plus optional live availability and
freshness signals. Organization-neutral.

Route schema version 2 is additive: existing top-level fields and deprecated
``prompt_authorizes_execution`` are preserved for the current contract cycle.
"""

from __future__ import annotations

import re
from typing import Any

from .canonical_tool_specs import KNOWN_TOOL_GROUPS
from .tool_family_manifest import family_record
from .tool_metadata_types import ROUTE_SCHEMA_VERSION
from .workflow_recipe_manifest import WORKFLOWS, workflow_record

# Source-of-truth label per family (§10).
_SOURCE_OF_TRUTH: dict[str, str] = {
    "client_output_workspace": "generated outputs workspace (outputs root; NOT the vault)",
    "output_receipts_manifests": "generated outputs receipts/manifest",
    "artifact_workspace": "staged artifact proposals (not yet canonical)",
    "canonical_promotion": "canonical memory (Obsidian cards)",
    "obsidian_materialization": "canonical memory (Obsidian cards)",
    "assistant_decision_memory": "canonical decision/preference/open-loop records",
    "assistant_source_connector": "indexed source files",
    "assistant_navigation": "indexed source files + generated cards + vault notes",
    "assistant_context_packs": "durable context packs (source-backed)",
    "assistant_memory": "compiled memory (source-backed)",
    "assistant_research_packets": "research packets (citation-backed answer CONTEXT)",
    "assistant_answer_drafts": "citation-safe answer drafts (advisory)",
    "status_health": "server status (not content)",
    "tool_catalog_help_query": "tool catalog (not content)",
    "client_tool_manifest": "tool operating manifest",
    "prompt_routing": "routing manifests (advisory)",
}

_WRITE_CLASSES = frozenset({"staged_write", "canonical_promotion", "archive"})
_LAYER_ORDER = ("route_only", "metadata_discovery", "candidate_triage", "bounded_read", "deep_parse")

_MEMORY_CUES = (
    "remember that", "remember this", "for the future", "going forward", "from now on",
    "we decided", "i decided", "the decision is", "our preference", "i prefer", "always ",
    "never ", "make a note", "keep in mind", "standing rule",
)

_DESTRUCTIVE_VERBS = ("delete", "remove", "wipe", "destroy", "erase", "purge", "rm -")
_DESTRUCTIVE_OBJECTS = ("vault", "note", "file", "readme", "card", "record", "folder", "document",
                        "page", ".md", "artifact", "output")

# Capability → workflow policies / trigger keywords that must not score under prohibition.
_CAPABILITY_POLICIES: dict[str, frozenset[str]] = {
    "promote": frozenset({"canonical_promotion"}),
    "write": frozenset({"staged_write", "canonical_promotion", "archive"}),
    "stage": frozenset({"staged_write"}),
    "archive": frozenset({"archive"}),
    "execute": frozenset({"staged_write", "canonical_promotion", "archive"}),
    "execute_non_read": frozenset({"staged_write", "canonical_promotion", "archive"}),
    "index": frozenset(),  # handled via must_not / constraints
    "deploy": frozenset(),
    "external_action": frozenset(),
}

# Keywords that indicate a workflow exercises a capability (for scoring blocks).
_CAPABILITY_TRIGGER_TOKENS: dict[str, tuple[str, ...]] = {
    "promote": ("promote", "make canonical", "finalize the decision", "apply promotion", "canonical"),
    "write": ("write", "create the file", "save as", "generate a", "commit the", "export"),
    "stage": ("stage", "staging"),
    "archive": ("archive",),
    "execute": ("execute", "go ahead and", "send it", "run the"),
    "index": ("reindex", "rebuild index", "refresh index"),
    "deploy": ("deploy", "restart the nas"),
    "external_action": ("send it", "send email", "send the", "email this"),
}

# Negators that open a prohibition window (clause-scoped).
_NEGATOR_PATTERNS = (
    r"\bdo not\b", r"\bdon't\b", r"\bnever\b", r"\bwithout\b", r"\bnot a\b",
    r"\bno write\b", r"\bno staging\b", r"\bno stage\b", r"\bno promote\b",
    r"\bplan only\b", r"\bread-only\b", r"\bread only\b",
)
_CLAUSE_SPLIT = re.compile(r"[.;\n]|,\s+and\b")
# Window after negator: tokens to scan for capability words.
_PROHIBITION_WINDOW = 12

# Explicit allow-read phrases even when execute is banned.
_ALLOW_READ_PHRASES = (
    "you may use read-only", "read-only tools", "beyond read-only", "beyond read only",
    "read only analysis", "read-only analysis", "may use read-only", "read-only analysis",
)


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def _is_destructive(prompt_l: str) -> bool:
    return (any(v in prompt_l for v in _DESTRUCTIVE_VERBS)
            and any(o in prompt_l for o in _DESTRUCTIVE_OBJECTS))


def _is_read_only_posture(prompt_l: str) -> bool:
    """True when the operator frames the request as read-only work (not plan-only identify)."""
    return bool(re.search(r"\bread[- ]only\b", prompt_l))


def _extract_prohibitions(prompt_l: str) -> set[str]:
    """Return capability names prohibited by scoped negation (not keyword-wide).

    Critical: ``read-only`` authorizes bounded *read* tool calls. It must never be converted
    into a generic ``execute`` prohibition. Only an explicit ``do not execute`` / ``plan only``
    (without a beyond-read-only exception) bans non-advisory tool execution.
    """
    prohibitions: set[str] = set()

    # Explicit execute bans (not implied by "read-only").
    # Vocabulary:
    # - ``execute`` — no tool calls (plan-only / identify-only)
    # - ``execute_non_read`` — ban write/stage/promote/external/etc., allow bounded reads
    beyond_read_only = bool(re.search(r"\bbeyond read[- ]only\b", prompt_l))
    if re.search(r"\bplan only\b", prompt_l):
        prohibitions.add("execute")
    if re.search(r"\bdo not execute\b", prompt_l) or re.search(r"\bdon't execute\b", prompt_l):
        if beyond_read_only:
            prohibitions.add("execute_non_read")
            prohibitions.update({"write", "stage", "promote", "external_action"})
        else:
            prohibitions.add("execute")

    # Read-only posture: ban mutation classes when listed.
    # Never add ``execute`` here — bounded read execution is the requested operation.
    if _is_read_only_posture(prompt_l):
        for cap, patterns in (
            ("write", (r"\bwrite\b", r"\bmutat", r"\bno write\b")),
            ("stage", (r"\bstage\b", r"\bstaging\b")),
            ("promote", (r"\bpromote\b", r"\bpromotion\b")),
            ("index", (r"\bindex\b", r"\breindex\b", r"\brefresh\b")),
            ("deploy", (r"\bdeploy\b",)),
            ("archive", (r"\barchive\b",)),
            ("external_action", (r"\bsend\b", r"\bemail\b")),
        ):
            if any(re.search(p, prompt_l) for p in patterns):
                prohibitions.add(cap)
        if re.search(r"\bmutat", prompt_l):
            prohibitions.add("write")
        # "do not execute any action" under read-only identify: still ban mutation classes
        if re.search(r"\bdo not execute any action\b", prompt_l) or re.search(
            r"\b(do not|don't) execute\b", prompt_l
        ):
            prohibitions.update({"write", "stage", "promote", "external_action"})

    # Phrase-level bans (capability-specific; do not fold write→execute).
    for phrase, caps in (
        (r"\bno write\b", {"write"}),
        (r"\bno staging\b", {"stage"}),
        (r"\bno stage\b", {"stage"}),
        (r"\bdo not write\b", {"write"}),
        (r"\bdon't write\b", {"write"}),
        (r"\bwithout writing\b", {"write"}),
        (r"\bdo not stage\b", {"stage"}),
        (r"\bdo not promote\b", {"promote"}),
        (r"\bdon't promote\b", {"promote"}),
        (r"\bnever promote\b", {"promote"}),
        (r"\bdo not deploy\b", {"deploy"}),
        (r"\bdo not\b[^\n.]{0,40}\bindex\b", {"index"}),
        (r"\bdo not\b[^\n.]{0,40}\brefresh\b", {"index"}),
        (r"\bdo not\b[^\n.]{0,40}\bmutat", {"write"}),
    ):
        if re.search(phrase, prompt_l):
            prohibitions.update(caps)

    # Clause-scoped: negator + nearby capability token within a bounded window.
    clauses = _CLAUSE_SPLIT.split(prompt_l)
    for clause in clauses:
        c = clause.strip()
        if not c:
            continue
        if re.search(r"\bnot a\b", c) and "receipt" in c:
            continue
        if re.search(r"\bwithout\b", c) and not any(
            tok in c for tok in ("write", "promot", "stag", "execut", "deploy", "index")
        ):
            continue
        # "read-only" is a posture marker, not a capability negator by itself.
        if re.fullmatch(r"read[- ]only[:.]?", c) or c.startswith("read-only") and "do not" not in c:
            if "do not" not in c and "don't" not in c and "never" not in c:
                continue

        tokens = c.split()
        for i, tok in enumerate(tokens):
            window_text = " ".join(tokens[i:i + 3])
            # Do NOT treat bare "read-only" / "read" as negators — that caused execute false positives.
            is_neg = bool(re.match(r"^(do|don't|never|without|not|no|plan)$", tok)) or any(
                re.search(p, window_text) for p in (
                    r"\bdo not\b", r"\bdon't\b", r"\bnever\b", r"\bwithout\b",
                    r"\bnot a\b", r"\bno write\b", r"\bno staging\b", r"\bplan only\b",
                )
            )
            if not is_neg:
                continue
            span = " ".join(tokens[i:i + _PROHIBITION_WINDOW])
            # "beyond read-only" exception: ban non-read classes only (never generic ``execute``).
            if "beyond read-only" in span or "beyond read only" in span:
                prohibitions.add("execute_non_read")
                prohibitions.update({"write", "stage", "promote", "external_action"})
                continue
            for cap, cap_tokens in _CAPABILITY_TRIGGER_TOKENS.items():
                if any(ct in span for ct in cap_tokens):
                    if cap == "promote" and "receipt" in span and "not a" in span:
                        continue
                    if cap == "execute" and beyond_read_only:
                        prohibitions.add("execute_non_read")
                        continue
                    prohibitions.add(cap)

    # Posture cleanup: read-only work must not carry a naked execute ban unless plan-only/identify.
    if beyond_read_only or (
        _is_read_only_posture(prompt_l)
        and not re.search(r"\bplan only\b", prompt_l)
        and not re.search(r"\b(identify which tool|which tool should be used)\b", prompt_l)
    ):
        prohibitions.discard("execute")
        if beyond_read_only:
            prohibitions.add("execute_non_read")
            prohibitions.update({"write", "stage", "promote", "external_action"})

    return prohibitions


def _score_workflow(prompt_l: str, wf: dict[str, Any], prohibitions: set[str] | None = None) -> int:
    """Score workflow; triggers nested under prohibited capabilities do not add points."""
    prohibitions = prohibitions if prohibitions is not None else set()
    policy = wf.get("operator_authorization_policy", "read")
    # Entire workflow banned by policy prohibition.
    for cap in prohibitions:
        banned_policies = _CAPABILITY_POLICIES.get(cap, frozenset())
        if policy in banned_policies:
            return 0
        # Promote workflows also matched by promote triggers under prohibition.
        if cap == "promote" and policy == "canonical_promotion":
            return 0
        if cap == "external_action" and "external" in wf.get("workflow_id", ""):
            return 0

    score = 0
    for phrase in wf["trigger_phrases"]:
        p = phrase.lower()
        if not p or p not in prompt_l:
            continue
        # If this phrase is itself a capability token under prohibition, skip.
        skip = False
        for cap in prohibitions:
            for ct in _CAPABILITY_TRIGGER_TOKENS.get(cap, ()):
                if ct in p or p in ct:
                    skip = True
                    break
            if skip:
                break
        if skip:
            continue
        score += 2 if " " in p else 1
    return score


_INTENT_TIE_TIER: dict[str, int] = {
    "capture": 0, "documentation": 0, "staged_write": 1, "generation": 2, "canonical_promotion": 3,
}
_DEFAULT_INTENT_TIER = 5


def _intent_tier(wf: dict[str, Any]) -> int:
    return min((_INTENT_TIE_TIER.get(ic, _DEFAULT_INTENT_TIER) for ic in wf["intent_classes"]),
               default=_DEFAULT_INTENT_TIER)


def _rank_workflows(
    prompt_l: str, prohibitions: set[str] | None = None,
) -> list[tuple[int, dict[str, Any]]]:
    prohibitions = prohibitions if prohibitions is not None else set()
    scored = [(_score_workflow(prompt_l, wf, prohibitions), wf) for wf in WORKFLOWS]
    scored = [(s, wf) for s, wf in scored if s > 0]
    scored.sort(key=lambda t: (-t[0], _intent_tier(t[1]), t[1]["workflow_id"]))
    return scored


def _retrieval_budget(wf: dict[str, Any], has_exact_id: bool) -> dict[str, Any]:
    layer = wf["default_retrieval_layer"]
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


def _plan_only_or_no_execute(prompt_l: str, prohibitions: set[str]) -> bool:
    """True when the prompt forbids tool *calls* (identify-only / plan-only).

    Read-only audits are NOT plan-only: they authorize bounded read tool calls.
    """
    # Identify-which-tool + do not execute → advisory only (no tool calls).
    if re.search(r"\b(identify which tool|which tool should be used)\b", prompt_l):
        if re.search(r"\b(do not execute|don't execute|do not run|do not execute any action)\b", prompt_l):
            return True
    if re.search(r"\bplan only\b", prompt_l):
        return True
    if re.search(r"\bdo not execute any action\b", prompt_l):
        return True
    # Bare "do not execute" without read-only posture and without beyond-read-only allow.
    if re.search(r"\b(do not|don't) execute\b", prompt_l):
        if _is_read_only_posture(prompt_l) or re.search(r"\bbeyond read[- ]only\b", prompt_l):
            # Read-only analysis / beyond-read-only still allows read tool calls.
            return False
        return True
    return False


def _reads_explicitly_allowed(prompt_l: str) -> bool:
    if any(p in prompt_l for p in _ALLOW_READ_PHRASES):
        return True
    if re.search(r"\bbeyond read[- ]only\b", prompt_l):
        return True
    # A read-only posture (audit/analysis) authorizes bounded reads.
    if _is_read_only_posture(prompt_l) and not _plan_only_or_no_execute(prompt_l, set()):
        return True
    return False


# Schema-aligned required args for tools when live schema index is empty (offline tests).
_TOOL_REQUIRED_ARGS: dict[str, tuple[str, ...]] = {
    "assistant_get_decision": ("decision_id",),
    "assistant_get_preference": ("preference_id",),
    "assistant_get_open_loop": ("open_loop_id",),
    "pa_artifact_proposal_stage": ("session_id", "candidate_artifacts"),
    "pa_artifact_promotion_apply": ("promotion_bundle_id", "operator_approval_id"),
    "pa_output_commit": ("output_id", "operator_approval_id"),
    "assistant_source_file_read": ("source_id",),
}


def required_args_for_tool(tool_name: str) -> list[str]:
    """Return required argument names (live schema when available; static fallback)."""
    try:
        from hb_assistant.nas_mcp.tool_registration import (  # noqa: PLC0415
            derive_tool_arg_meta,
            live_tool_schema_index,
        )

        meta = derive_tool_arg_meta(tool_name, live_tool_schema_index())
        req = meta.get("required_args") or []
        if req:
            return [str(x) for x in req]
    except Exception:  # noqa: BLE001
        pass
    return list(_TOOL_REQUIRED_ARGS.get(tool_name, ()))


def _extract_topic_query(prompt_l: str) -> str | None:
    """Best-effort topical fragment (e.g. 'about X' / 'for X'); not an ID."""
    m = re.search(r"\b(?:about|for|regarding|on)\s+([a-z0-9][\w\-]{0,64})\b", prompt_l)
    if m:
        return m.group(1)
    return None


def _extract_validated_id(prompt: str, arg_name: str) -> str | None:
    """Extract a workflow-specific ID only when pattern matches repo contracts. Never invent."""
    # Conservative patterns aligned to PA IDs (alphanumeric with optional prefix/hyphen/underscore).
    patterns = {
        "decision_id": r"\b((?:dec|decision)[_-]?[a-z0-9][a-z0-9_\-]{3,64})\b",
        "preference_id": r"\b((?:pref|preference)[_-]?[a-z0-9][a-z0-9_\-]{3,64})\b",
        "open_loop_id": r"\b((?:ol|open[_-]?loop)[_-]?[a-z0-9][a-z0-9_\-]{3,64})\b",
        "operator_approval_id": r"\b((?:appr|approval)[_-]?[a-z0-9][a-z0-9_\-]{6,64})\b",
        "promotion_bundle_id": r"\b((?:promob|promotion[_-]?bundle)[_-]?[a-z0-9][a-z0-9_\-]{6,64})\b",
        "session_id": r"\b((?:sess|session)[_-]?[a-z0-9][a-z0-9_\-]{6,64})\b",
        "source_id": r"\b((?:src|source)[_-]?[a-z0-9][a-z0-9_\-]{6,64})\b",
    }
    pat = patterns.get(arg_name)
    if not pat:
        return None
    m = re.search(pat, prompt, flags=re.I)
    if not m:
        return None
    return m.group(1)


def _authorization(
    wf: dict[str, Any],
    confident: bool,
    *,
    prompt_l: str,
    prohibitions: set[str],
    next_tool: str | None = None,
    next_arguments: dict[str, Any] | None = None,
    has_exact_id: bool = False,
) -> dict[str, Any]:
    """Multi-dimensional authorization + request-level executability (does not execute)."""
    action_class = wf["operator_authorization_policy"]
    is_write = action_class in _WRITE_CLASSES
    plan_only = _plan_only_or_no_execute(prompt_l, prohibitions)
    allow_read = not plan_only  # supporting reads for write workflows included

    non_read_banned = "execute_non_read" in prohibitions or "execute" in prohibitions
    staging_ok = (
        action_class == "staged_write"
        and "stage" not in prohibitions
        and "write" not in prohibitions
        and not non_read_banned
        and not plan_only
    )
    write_ok = (
        action_class == "staged_write"
        and "write" not in prohibitions
        and not non_read_banned
        and not plan_only
        and confident
    )
    # Prompt may request promotion without satisfying approval — permission is separate.
    promote_requested = action_class == "canonical_promotion" and "promote" not in prohibitions and not plan_only
    promote_perm = promote_requested  # prompt_permission.promote
    promotion_authorized = False  # not cleared for execution without validation+approval
    external_ok = False
    if "external_action" in prohibitions:
        external_ok = False

    additional_approval = bool(
        action_class in ("canonical_promotion", "archive")
        or bool(wf.get("additional_approval_points"))
        or (action_class == "staged_write" and next_tool and "commit" in (next_tool or ""))
    )
    # Stage tools do not require approval IDs; commit/promote do.
    tool_needs_approval = bool(
        next_tool and (
            next_tool in ("pa_artifact_promotion_apply", "pa_tool_manifest_refresh_promote", "pa_output_commit")
            or next_tool.endswith("_commit")
            or "promotion_apply" in next_tool
        )
    )
    approval_points = list(wf["additional_approval_points"])
    approval_satisfied = False  # preflight never holds server-minted approval

    next_arguments = dict(next_arguments or {})
    req_args = required_args_for_tool(next_tool) if next_tool else []
    missing = [a for a in req_args if next_arguments.get(a) in (None, "", [], {})]
    # has_exact_id alone never invents IDs — only reduces ambiguity when args already present.
    if has_exact_id and missing and not any(_extract_validated_id(prompt_l, a) for a in missing):
        pass  # still missing

    # --- precedence for primary blocker ---
    blocked_reason: str | None = None
    currently_executable = False
    approval_required_flag = False

    if plan_only or "execute" in prohibitions and not allow_read:
        blocked_reason = "plan_only" if plan_only else "operation_prohibited"
    elif next_tool is None:
        blocked_reason = "no_recommended_tool"
    elif missing:
        blocked_reason = "missing_arguments"
        # If only approval-shaped args remain among missing after non-approval filled, note approval.
        non_appr_missing = [a for a in missing if a != "operator_approval_id"]
        if not non_appr_missing and "operator_approval_id" in missing:
            blocked_reason = "approval_required"
            approval_required_flag = True
        elif tool_needs_approval:
            approval_required_flag = True
    elif tool_needs_approval and not approval_satisfied:
        blocked_reason = "approval_required"
        approval_required_flag = True
    elif promote_requested and not approval_satisfied:
        # Non-approval target args may still be missing; if not in missing list above, approval.
        blocked_reason = "approval_required"
        approval_required_flag = True
    elif not allow_read and not staging_ok and not write_ok and not promote_perm:
        blocked_reason = "not_authorized"
    else:
        currently_executable = True
        blocked_reason = None

    # Stage: never attribute approval when stage tool only needs session/artifacts.
    if next_tool == "pa_artifact_proposal_stage" and missing:
        blocked_reason = "missing_arguments"
        approval_required_flag = False
        currently_executable = False

    prompt_authorizes_execution = bool(allow_read and not plan_only and not is_write)

    return {
        "action_class": action_class,
        "write_risk": wf["write_risk"],
        "requested_operation_class": action_class if action_class != "read" else "read",
        "operation_requested": action_class,
        "prompt_permission": {
            "read": allow_read,
            "stage": staging_ok,
            "write": write_ok,
            "promote": promote_perm,
            "external_action": external_ok,
        },
        "server_policy_permission": {
            "read": True,
            "stage": action_class == "staged_write",
            "write": action_class in _WRITE_CLASSES,
            "promote": action_class == "canonical_promotion",
            "external_action": False,
        },
        "approval_satisfied": approval_satisfied,
        "approval_required": approval_required_flag or tool_needs_approval,
        "currently_executable": currently_executable,
        "execution_blocked_reason": blocked_reason,
        "missing_required_arguments": missing,
        "read_tool_calls_authorized": allow_read and not plan_only,
        "advisory_planning_authorized": True,
        "staging_authorized": staging_ok,
        "external_action_authorized": external_ok,
        "write_authorized": False,  # commit never authorized by prompt alone
        "promotion_authorized": promotion_authorized,
        "additional_approval_required": additional_approval or tool_needs_approval,
        "requires_explicit_operator_go": bool(is_write),
        "approval_points": approval_points,
        "prohibitions": sorted(prohibitions),
        "prompt_authorizes_execution": prompt_authorizes_execution,
        "prompt_authorizes_execution_deprecated": True,
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
        "unsafe_fallback_blocked": is_write,
        "failure_recovery": wf["failure_recovery"],
        "tool": "hb_assistant_tool_query",
        "arguments_template": {
            "tool_name": (wf["tool_sequence"][0] if wf.get("tool_sequence") else "pa_prompt_route"),
            "arguments": {},
        },
    }


def _tool_group(name: str, tool_groups: dict[str, str | None] | None = None) -> str | None:
    if tool_groups and name in tool_groups and tool_groups[name] is not None:
        return tool_groups[name]
    return KNOWN_TOOL_GROUPS.get(name)


def _enrich_tool_steps(
    tools: list[str],
    *,
    available_tools: frozenset[str] | set[str] | None,
    authorization: dict[str, Any],
    primary_family: str,
    tool_groups: dict[str, str | None] | None = None,
    next_tool: str | None = None,
    next_arguments: dict[str, Any] | None = None,
    topic_query: str | None = None,
) -> list[dict[str, Any]]:
    from .tool_family_manifest import family_for_tool  # noqa: PLC0415

    steps: list[dict[str, Any]] = []
    for i, t in enumerate(tools):
        group = _tool_group(t, tool_groups)
        available = True if available_tools is None else t in available_tools
        fam = family_for_tool(t, group) or primary_family
        args: dict[str, Any] = {}
        if t == next_tool and next_arguments:
            args = dict(next_arguments)
        # List/discovery tools: do not inject unsupported query args; surface topic separately.
        req = required_args_for_tool(t)
        missing = [a for a in req if args.get(a) in (None, "", [], {})]
        is_next = (t == next_tool) or (i == 0)
        step_auth = bool(authorization.get("read_tool_calls_authorized"))
        if t.startswith("pa_artifact") or "stage" in t or "session_capture" in t:
            step_auth = bool(
                authorization.get("staging_authorized")
                or authorization.get("read_tool_calls_authorized")
            )
        if "promotion_apply" in t or t == "ai_outputs_card_upsert":
            step_auth = bool(authorization.get("prompt_permission", {}).get("promote"))
        # Executability only for the next_step tool with full preconditions.
        if is_next:
            cex = bool(authorization.get("currently_executable")) and available and step_auth
            blocked = None if cex else (
                authorization.get("execution_blocked_reason")
                or ("missing_arguments" if missing else "not_authorized")
            )
        else:
            # Subsequent getter/list steps are not currently executable until prior selection.
            cex = False
            blocked = "awaiting_prior_step" if not missing else "missing_arguments"
        step: dict[str, Any] = {
            "tool": t,
            "tool_group": group,
            "family": fam,
            "surface": group,
            "arguments": args,
            "call_mode": "direct" if available else "gateway",
            "available": available,
            "installed": available,
            "profile_enabled": available,
            "directly_exposed": available,
            "gateway_allowlisted": True,
            "server_policy_available": available,
            "authorized": step_auth and available,
            "authorization_reason": (
                "authorized" if step_auth and available
                else (blocked or "not_authorized")
            ),
            "currently_executable": cex,
            "execution_blocked_reason": blocked,
            "missing_required_arguments": missing,
        }
        if topic_query and t.startswith("assistant_list_"):
            step["topic_query"] = topic_query
            step["topical_discovery_supported"] = False
            step["topic_guidance"] = (
                f"List filters by type/status only; apply topic '{topic_query}' when selecting "
                f"from the bounded result set."
            )
        steps.append(step)
    return steps


def _freshness_view(freshness: dict[str, Any] | None, is_write: bool) -> dict[str, Any]:
    if not freshness:
        return {"checked": False, "stale": False, "staleness_state": "unknown",
                "warnings": [], "write_blocked_by_staleness": False}
    state = str(freshness.get("staleness_state") or "unknown")
    # Honest failure: check_failed / indeterminate never report as current.
    if state in ("check_failed", "indeterminate", "unknown") and freshness.get("check_error"):
        stale = True
    else:
        stale = bool(freshness.get("stale"))
    return {
        "checked": True,
        "stale": stale,
        "staleness_state": state,
        "warnings": list(freshness.get("warnings", [])),
        "write_blocked_by_staleness": bool(stale and is_write),
        "categories": freshness.get("categories") or {},
    }


def route_prompt(
    prompt: str,
    *,
    available_tools: frozenset[str] | set[str] | None = None,
    has_exact_id: bool = False,
    freshness: dict[str, Any] | None = None,
    tool_groups: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Return a read-only route plan for ``prompt`` (schema v2, additive). Never writes or reads content."""
    prompt_l = _norm(prompt)
    prohibitions = _extract_prohibitions(prompt_l)

    if _is_destructive(prompt_l):
        return _destructive_route(prompt, prompt_l, freshness, prohibitions)

    if any(c in prompt_l for c in ("show me secrets", "show tokens", "dump credentials", "api keys",
                                   "extract password")):
        return _safety_refusal_route(
            prompt, prompt_l, freshness, prohibitions,
            intent="secret_extraction_refusal",
            rationale="Refuse secret/token extraction.",
        )
    if any(c in prompt_l for c in ("write a file to /tmp", "write to /tmp", "/tmp/anything",
                                   "save to /etc/")):
        return _safety_refusal_route(
            prompt, prompt_l, freshness, prohibitions,
            intent="arbitrary_path_write_refusal",
            rationale="Refuse arbitrary host path writes; use generated-output workspace only.",
        )

    # Negated noun assertions ("this is not a promotion receipt") are not retrieval intents.
    if _is_negated_noun_assertion(prompt_l):
        return _negated_assertion_route(prompt, prompt_l, freshness, prohibitions)

    # Ambiguous bare "notes" without vault/source/project cue → clarify once.
    if _is_ambiguous_notes(prompt_l):
        return _ambiguous_notes_route(prompt, prompt_l, freshness, prohibitions)

    ranked = _rank_workflows(prompt_l, prohibitions)

    if not ranked:
        return _unknown_route(prompt, prompt_l, freshness, prohibitions)

    best_score, best_wf = ranked[0]
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
    if best_score >= 3 or (best_score >= 2 and best_score - runner_up >= 2):
        confidence = "high"
    elif best_score >= 2 or (best_score == 1 and len(candidate_families) == 1):
        confidence = "medium"
    else:
        confidence = "low"
    confident = confidence in ("high", "medium")

    seq = list(best_wf["tool_sequence"])
    if available_tools is not None:
        unavailable = [t for t in seq if t not in available_tools]
        recommended_tools = [t for t in seq if t in available_tools]
    else:
        unavailable = []
        recommended_tools = seq
    workflow_available = not unavailable

    topic = _extract_topic_query(prompt_l)
    next_tool = recommended_tools[0] if recommended_tools else None
    next_args: dict[str, Any] = {}
    # Populate only validated extracted IDs for the *next* tool's required args.
    if next_tool:
        for arg in required_args_for_tool(next_tool):
            extracted = _extract_validated_id(prompt, arg)
            if extracted:
                next_args[arg] = extracted
    # has_exact_id never invents: if set without extractable ID, args stay empty.

    action_class = best_wf["operator_authorization_policy"]
    is_write = action_class in _WRITE_CLASSES
    authorization = _authorization(
        best_wf, confident,
        prompt_l=prompt_l, prohibitions=prohibitions,
        next_tool=next_tool, next_arguments=next_args, has_exact_id=has_exact_id,
    )
    if available_tools is not None and next_tool and next_tool not in available_tools:
        authorization = dict(authorization)
        authorization["currently_executable"] = False
        authorization["execution_blocked_reason"] = "surface_unavailable"

    fam = family_record(primary_family) or {}

    tool_steps = _enrich_tool_steps(
        recommended_tools,
        available_tools=available_tools,
        authorization=authorization,
        primary_family=primary_family,
        tool_groups=tool_groups,
        next_tool=next_tool,
        next_arguments=next_args,
        topic_query=topic,
    )

    next_step = tool_steps[0] if tool_steps else None
    additional_steps = tool_steps[1:] if len(tool_steps) > 1 else []

    constraints = [f"prohibited:{c}" for c in sorted(prohibitions)]
    must_not = list(best_wf["must_not_use"]) + list(fam.get("family_level_negative_instructions", []))
    if prohibitions:
        must_not = must_not + [f"prompt prohibits: {', '.join(sorted(prohibitions))}"]
    # Topical discovery limitation for list tools without a query arg.
    if topic and next_tool and next_tool.startswith("assistant_list_"):
        constraints.append(
            f"topic_query={topic}; list tools filter by type/status only — "
            f"apply topic '{topic}' when selecting from the bounded list "
            f"(topical discovery arg not supported on {next_tool})."
        )

    plan: dict[str, Any] = {
        "route_schema_version": ROUTE_SCHEMA_VERSION,
        "prompt": prompt,
        "intent": {
            "primary_class": best_wf["intent_classes"][0] if best_wf["intent_classes"] else "unknown",
            "classes": list(best_wf["intent_classes"]),
        },
        "source_of_truth": best_wf.get("source_of_truth") or _SOURCE_OF_TRUTH.get(primary_family, "unclassified"),
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
        "must_not_use": must_not,
        "fallback_plan": _fallback_plan(best_wf, is_write),
        "route_confidence": confidence,
        "routing_rationale": (
            f"Matched workflow '{best_wf['workflow_id']}' (score {best_score}) in family '{primary_family}'; "
            f"source of truth = {_SOURCE_OF_TRUTH.get(primary_family, 'unclassified')}."
        ),
        "clarifying_question": None,
        "preflight_is_read_only": True,
        "constraints": constraints,
        "warnings": list(constraints),
        "next_step": next_step,
        "additional_steps": additional_steps,
        "route": {
            "intent": (best_wf["intent_classes"][0] if best_wf["intent_classes"] else "unknown"),
            "source_of_truth": best_wf.get("source_of_truth") or _SOURCE_OF_TRUTH.get(primary_family, "unclassified"),
            "family": primary_family,
            "workflow": best_wf["workflow_id"],
            "confidence": confidence,
        },
    }

    if not confident and is_write:
        plan["clarifying_question"] = (
            f"This looks like a '{action_class}' action but intent is ambiguous. Confirm the target "
            f"(e.g. generated file vs canonical memory) before I stage anything."
        )
        plan["recommended_tools"] = []
        plan["recommended_workflow"] = "context_preflight"
        plan["next_step"] = None
        plan["additional_steps"] = []

    # "Go ahead and send it" without external tool → do not invent.
    if re.search(r"\b(go ahead and send|send it|email this)\b", prompt_l):
        plan["warnings"] = list(plan.get("warnings") or []) + [
            "No external-action tool is available; do not invent send/email execution.",
        ]
        plan["authorization"]["external_action_authorized"] = False
        plan["authorization"]["currently_executable"] = False
        if best_wf["workflow_id"].startswith("generate_") or "send" in prompt_l:
            # Keep advisory only.
            pass

    plan["freshness"] = _freshness_view(freshness, is_write)
    return plan


def _is_negated_noun_assertion(prompt_l: str) -> bool:
    """True for sentences that deny a noun label rather than request work.

    Example: "this is not a promotion receipt" — not a request to inspect receipts.
    """
    if re.search(r"\b(this is not a|that is not a|it's not a|it is not a|not a)\b", prompt_l):
        # Assertion about identity/classification, not an imperative request verb.
        if not re.search(
            r"\b(find|search|get|list|show|open|retrieve|inspect|read|stage|promote|create|write)\b",
            prompt_l,
        ):
            return True
        # Even with a verb, "this is not a X" is typically classification.
        if re.search(r"\bthis is not a\b", prompt_l) or re.search(r"\bthat is not a\b", prompt_l):
            return True
    return False


def _negated_assertion_route(
    prompt: str, prompt_l: str, freshness: dict[str, Any] | None, prohibitions: set[str],
) -> dict[str, Any]:
    base = _unknown_route(prompt, prompt_l, freshness, prohibitions)
    base["intent"] = {"primary_class": "negated_assertion", "classes": ["negated_assertion", "clarification"]}
    base["routing_rationale"] = (
        "Negated noun assertion detected (e.g. 'this is not a …'); not a tool/retrieval request."
    )
    base["clarifying_question"] = (
        "Understood as a classification statement, not a tool request. "
        "What would you like to do instead (retrieve, stage, review, or something else)?"
    )
    base["recommended_workflow"] = "context_preflight"
    base["recommended_tools"] = []
    base["next_step"] = None
    base["additional_steps"] = []
    base["route_confidence"] = "high"
    base["route"] = {
        "intent": "negated_assertion", "source_of_truth": "unclassified",
        "family": "prompt_routing", "workflow": "context_preflight", "confidence": "high",
    }
    return base


def _is_ambiguous_notes(prompt_l: str) -> bool:
    """Bare 'notes' without vault/source/project cue → one clarification."""
    if "notes" not in prompt_l:
        return False
    if any(k in prompt_l for k in (
        "vault", "obsidian", "meeting notes", "source", "nas", "work files",
        "project notes", "project file", "indexed",
    )):
        return False
    # Exactly vague patterns like "find my notes" / "handle notes"
    return bool(re.search(r"\b(find|search|get|show)\b.*\bnotes\b", prompt_l)) and "project" not in prompt_l


def _ambiguous_notes_route(
    prompt: str, prompt_l: str, freshness: dict[str, Any] | None, prohibitions: set[str],
) -> dict[str, Any]:
    base = _unknown_route(prompt, prompt_l, freshness, prohibitions)
    base["intent"] = {"primary_class": "ambiguous_notes", "classes": ["ambiguous_notes", "retrieval"]}
    base["clarifying_question"] = (
        "Do you mean Obsidian vault notes, indexed NAS project files, or generated cards?"
    )
    base["routing_rationale"] = "Ambiguous 'notes' without vault/source cue; ask one clarification."
    base["route_confidence"] = "low"
    return base


def _base_auth_read_only(prohibitions: set[str], *, allow_read: bool = False) -> dict[str, Any]:
    # Clarify routes recommend no tools — not currently executable even if reads are permitted.
    blocked = None if allow_read else "not_authorized"
    if allow_read:
        blocked = "no_recommended_tool"  # clarification / empty tool sequence
    return {
        "action_class": "read",
        "write_risk": "none",
        "requested_operation_class": "read",
        "operation_requested": "read",
        "prompt_permission": {
            "read": allow_read, "stage": False, "write": False, "promote": False, "external_action": False,
        },
        "server_policy_permission": {
            "read": True, "stage": False, "write": False, "promote": False, "external_action": False,
        },
        "approval_satisfied": True,
        "currently_executable": False,
        "execution_blocked_reason": blocked if not allow_read else "no_recommended_tool",
        "read_tool_calls_authorized": allow_read,
        "advisory_planning_authorized": True,
        "staging_authorized": False,
        "external_action_authorized": False,
        "write_authorized": False,
        "promotion_authorized": False,
        "additional_approval_required": False,
        "requires_explicit_operator_go": False,
        "approval_points": [],
        "prohibitions": sorted(prohibitions),
        "prompt_authorizes_execution": allow_read,
        "prompt_authorizes_execution_deprecated": True,
    }


def _unknown_route(
    prompt: str, prompt_l: str, freshness: dict[str, Any] | None, prohibitions: set[str] | None = None,
) -> dict[str, Any]:
    prohibitions = prohibitions if prohibitions is not None else _extract_prohibitions(prompt_l)
    allow_read = _reads_explicitly_allowed(prompt_l) and not _plan_only_or_no_execute(prompt_l, prohibitions)
    if _reads_explicitly_allowed(prompt_l):
        allow_read = True
    return {
        "route_schema_version": ROUTE_SCHEMA_VERSION,
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
        "authorization": _base_auth_read_only(prohibitions, allow_read=allow_read),
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
        "constraints": [f"prohibited:{c}" for c in sorted(prohibitions)],
        "warnings": [],
        "next_step": None,
        "additional_steps": [],
        "route": {
            "intent": "unknown", "source_of_truth": "unclassified", "family": "prompt_routing",
            "workflow": "context_preflight", "confidence": "low",
        },
        "freshness": _freshness_view(freshness, is_write=False),
    }


def _safety_refusal_route(
    prompt: str, prompt_l: str, freshness: dict[str, Any] | None, prohibitions: set[str],
    *, intent: str, rationale: str,
) -> dict[str, Any]:
    auth = _base_auth_read_only(prohibitions, allow_read=False)
    auth["additional_approval_required"] = True
    auth["requires_explicit_operator_go"] = True
    auth["approval_points"] = ["refusal — do not execute"]
    return {
        "route_schema_version": ROUTE_SCHEMA_VERSION,
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
        "authorization": auth,
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
        "constraints": [f"prohibited:{c}" for c in sorted(prohibitions)],
        "warnings": [],
        "next_step": None,
        "additional_steps": [],
        "route": {
            "intent": intent, "source_of_truth": "unclassified", "family": "prompt_routing",
            "workflow": "context_preflight", "confidence": "high",
        },
        "freshness": _freshness_view(freshness, is_write=False),
        "refused": True,
    }


def _destructive_route(
    prompt: str, prompt_l: str, freshness: dict[str, Any] | None, prohibitions: set[str],
) -> dict[str, Any]:
    auth = _base_auth_read_only(prohibitions | {"write", "execute"}, allow_read=False)
    auth["action_class"] = "destructive"
    auth["write_risk"] = "high"
    auth["requested_operation_class"] = "destructive"
    auth["additional_approval_required"] = True
    auth["requires_explicit_operator_go"] = True
    auth["approval_points"] = ["explicit operator confirmation of the exact target + irreversibility"]
    return {
        "route_schema_version": ROUTE_SCHEMA_VERSION,
        "prompt": prompt,
        "intent": {"primary_class": "destructive", "classes": ["destructive"]},
        "source_of_truth": "unclassified",
        "candidate_families": ["prompt_routing"],
        "primary_family": "prompt_routing",
        "recommended_workflow": "context_preflight",
        "alternative_workflows": [],
        "recommended_tools": [],
        "workflow_available": True,
        "unavailable_tools": [],
        "authorization": auth,
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
        "constraints": [f"prohibited:{c}" for c in sorted(prohibitions | {"write", "execute"})],
        "warnings": [],
        "next_step": None,
        "additional_steps": [],
        "route": {
            "intent": "destructive", "source_of_truth": "unclassified", "family": "prompt_routing",
            "workflow": "context_preflight", "confidence": "high",
        },
        "freshness": _freshness_view(freshness, is_write=True),
    }


def explain_route(prompt: str, **kwargs: Any) -> dict[str, Any]:
    """Route + attach the full workflow/family records (same normalized route as route_prompt)."""
    plan = route_prompt(prompt, **kwargs)
    wf = workflow_record(plan["recommended_workflow"])
    plan["workflow_detail"] = wf
    plan["family_detail"] = family_record(plan["primary_family"])
    return plan
