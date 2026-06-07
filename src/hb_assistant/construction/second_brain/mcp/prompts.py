"""Phase 08D reusable MCP prompts (Prompt 08).

Five named, parameterized prompt **templates** the client invokes. Each routes through
allowed tools only and bakes in the advisory / source-linked / review-controlled posture,
forbids final financial/legal/claim/entitlement/payment determinations, and instructs
against raw-store / writeback / policy-bypass / raw-prompt-persistence. Prompts are static
templates with argument substitution — they execute no tools and touch no data. Fail-closed
on any unknown prompt name; the prompt-registry snapshot is the audit artifact.
"""

from __future__ import annotations

import json
from typing import Any

from ..contracts import load_phase_08d_contract
from ..financial_review_routing import _assert_no_raw
from .policy import _policy_version
from .registry import load_allowed_tools
from .store import _sha256, write_mcp_prompt_registry_snapshot

# Phase 10A P09: raw posture for MCP prompts (baseline discourages raw; explicit raw packet tools are the allowed surface when policy permits)
try:
    from ..local_ai.contracts import load_raw_content_policy
except Exception:  # pragma: no cover
    load_raw_content_policy = None  # type: ignore

# Posture markers every rendered prompt must carry (asserted by the proof/tests).
_POSTURE = (
    "This is an advisory, source-linked, review-controlled assistant. "
    "Do not make final financial, legal, claim, entitlement, or payment determinations. "
    "Do not request raw stores, arbitrary SQL, raw files, or raw source content; "
    "do not perform or instruct any writeback; do not persist raw prompt or response text; "
    "and do not bypass Phase 08A/08B/08C policy. Surface review-required items for the "
    "operator; never present Tier-3 or high-impact items as final conclusions."
)

_PROMPT_POLICY_POSTURE = {
    "advisory_only": True,
    "source_linked": True,
    "review_controlled": True,
    "no_writeback": True,
    "no_raw": True,
    "no_final_determination": True,
    "no_policy_bypass": True,
}


def _compute_mcp_raw_allowed() -> bool:
    try:
        if load_raw_content_policy is None:
            return False
        rc = load_raw_content_policy()
        rcd = getattr(rc, "raw_content", None)
        downstream = getattr(rcd, "downstream", None) if rcd is not None else None
        flag = (
            bool(getattr(downstream, "mcp_allow_raw_content", False))
            if downstream is not None
            else False
        )
        mode = str(getattr(rcd, "mode", "") or "").lower() if rcd is not None else ""
        permissive = (
            mode in ("", "all_supported", "all_supported_plus_downstream") or "downstream" in mode
        )
        return bool(flag and permissive)
    except Exception:
        return False


def _arg(name: str, required: bool) -> dict[str, Any]:
    return {"name": name, "required": required}


# name -> (description, routes_through, forbidden, arguments, body_template)
_PROMPTS: dict[str, dict[str, Any]] = {
    "review_today_brief": {
        "description": "Review today's daily brief and its validation posture (advisory).",
        "routes_through": ["hb_get_daily_brief", "hb_validation_status"],
        "forbidden": "raw stores, final determinations, writeback",
        "arguments": [_arg("brief_date", False)],
        "body": (
            "Summarize today's brief for {brief_date} using only the hb_get_daily_brief and "
            "hb_validation_status tools. Report the bounded delivery status and validation "
            "posture; flag review-required items for the operator."
        ),
    },
    "ask_project_question": {
        "description": "Ask a source-linked project question (research-first; advisory).",
        "routes_through": ["hb_query", "hb_research_packet"],
        "forbidden": "arbitrary SQL, direct APIs, unsupported conclusions",
        "arguments": [_arg("question", True), _arg("project_key", False)],
        "body": (
            "Answer the question {question} for project {project_key} using only the "
            "hb_research_packet and hb_query tools. Research before answering; if context is "
            "insufficient, degrade or decline rather than overstate. Cite source families."
        ),
    },
    "prepare_for_meeting": {
        "description": "Prepare a source-linked meeting brief (advisory).",
        "routes_through": ["hb_research_packet", "hb_review_load_status", "hb_query"],
        "forbidden": "legal/claim/final decisions",
        "arguments": [_arg("meeting_topic", False), _arg("project_key", False)],
        "body": (
            "Prepare for the meeting on {meeting_topic} (project {project_key}) using only the "
            "hb_research_packet, hb_review_load_status, and hb_query tools. Provide a bounded, "
            "source-linked summary and the open review load; make no final decisions."
        ),
    },
    "review_memory_candidates": {
        "description": "Review proposed memory candidates and record feedback (advisory).",
        "routes_through": ["hb_memory_review_list", "hb_memory_feedback"],
        "forbidden": "raw source replay, preference overriding safety",
        "arguments": [_arg("project_key", False)],
        "body": (
            "List proposed memory candidates for project {project_key} with hb_memory_review_list "
            "and record operator feedback with hb_memory_feedback. Show only candidate metadata "
            "(no raw source replay); preferences never override safety."
        ),
    },
    "explain_review_load": {
        "description": "Explain the current review load and validation posture (advisory).",
        "routes_through": ["hb_review_load_status", "hb_validation_status"],
        "forbidden": "raw record inspection",
        "arguments": [_arg("project_key", False)],
        "body": (
            "Explain the current review load for project {project_key} using only the "
            "hb_review_load_status and hb_validation_status tools. Report counts by tier and "
            "the validation posture; do not inspect raw records."
        ),
    },
}


class PromptUnavailable(RuntimeError):
    """Raised when the prompt registry is missing/empty, drifts, or routes off-allowlist."""


def load_prompts() -> list[dict[str, Any]]:
    """Return the prompt registry (name/routes_through/forbidden) from the contract."""
    contract = load_phase_08d_contract("prompts_contract")
    prompts = contract.get("prompts") if isinstance(contract, dict) else None
    if not isinstance(prompts, list) or not prompts:
        raise PromptUnavailable("prompts registry missing or empty")
    contract_names = {str(p.get("name")) for p in prompts if isinstance(p, dict)}
    if contract_names != set(_PROMPTS):
        raise PromptUnavailable("prompt registry drift between contract and resolvers")
    allowed = set(load_allowed_tools())
    for name, spec in _PROMPTS.items():
        off = [t for t in spec["routes_through"] if t not in allowed]
        if off:
            raise PromptUnavailable(f"prompt {name} routes through non-allowed tools: {off}")
    return [
        {
            "name": str(p["name"]),
            "routes_through": list(p.get("routes_through", [])),
            "forbidden": p.get("forbidden"),
        }
        for p in prompts
        if isinstance(p, dict)
    ]


def _format(template: str, arguments: dict[str, Any]) -> str:
    # Substitute provided args; leave neutral placeholders for the rest (no raw values).
    class _Default(dict[str, Any]):
        def __missing__(self, key: str) -> str:
            return "(unspecified)"

    safe = _Default({k: str(v) for k, v in arguments.items() if v is not None})
    return template.format_map(safe)


def render_prompt(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Render one reusable prompt template (fail-closed on an unknown name)."""
    spec = _PROMPTS.get(name)
    if spec is None:
        return {
            "name": name,
            "status": "denied",
            "reason_code": "prompt_not_allowed",
            "fail_closed": True,
            "policy_posture": {
                **dict(_PROMPT_POLICY_POSTURE),
                "no_raw": not _compute_mcp_raw_allowed(),
                "mcp_raw_allowed": _compute_mcp_raw_allowed(),
            },
        }

    args = arguments or {}
    body = _format(str(spec["body"]), args)
    rendered = {
        "name": name,
        "description": spec["description"],
        "routes_through": list(spec["routes_through"]),
        "forbidden": spec["forbidden"],
        "arguments": list(spec["arguments"]),
        "posture": _POSTURE,
        "messages": [
            {"role": "system", "content": _POSTURE},
            {"role": "user", "content": body},
        ],
        "policy_posture": {
            **dict(_PROMPT_POLICY_POSTURE),
            "no_raw": not _compute_mcp_raw_allowed(),
            "mcp_raw_allowed": _compute_mcp_raw_allowed(),
        },
    }
    _assert_no_raw(json.dumps(rendered, default=str), f"mcp prompt {name}")
    return rendered


def render_all_prompts() -> list[dict[str, Any]]:
    """Render every registered prompt template."""
    return [render_prompt(name) for name in _PROMPTS]


def _registry_hash() -> str:
    return _sha256([(name, spec["routes_through"]) for name, spec in sorted(_PROMPTS.items())])


def snapshot_prompt_registry(*, db_path: str | None = None, persist: bool = True) -> str | None:
    """Persist a metadata-only prompt-registry snapshot (count + hash). Returns its id."""
    if not persist:
        return None
    return write_mcp_prompt_registry_snapshot(
        prompt_count=len(_PROMPTS),
        registry_hash=_registry_hash(),
        policy_version=_policy_version(),
        db_path=db_path,
    )
