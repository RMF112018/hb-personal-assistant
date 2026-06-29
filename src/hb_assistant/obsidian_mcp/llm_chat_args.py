"""Normalize public MCP argument names for LLM chat memory tools."""

from __future__ import annotations

from typing import Any

from .tools import ObsidianMcpToolError

_TRANSCRIPT_KEYS = frozenset(
    {
        "transcript",
        "transcript_text",
        "transcript_path",
        "max_chars",
        "redact",
        "operator_mode",
        "limit",
        "template_mode",
        "target_folder",
        "topic_domain",
        "routing_hint",
    }
)

_PLAN_KEYS = frozenset(
    {
        "transcript",
        "transcript_text",
        "transcript_path",
        "max_chars",
        "redact",
        "operator_mode",
        "conversation_title",
        "conversation_date",
        "source_platform",
        "source_model",
        "topic_domain",
        "knowledge_type",
        "sensitivity",
        "target_folder",
        "template_mode",
        "include_raw_transcript",
        "include_domain_specific_sections",
        "routing_hint",
        "project_hint",
        "workstream_hint",
        "topic_hint",
        "people_hint",
        "location_hint",
        "source_context_hint",
        "related_notes",
        "link_existing_notes",
    }
)

_TOPIC_PLAN_KEYS = _PLAN_KEYS | frozenset({"target_path"})

_APPLY_KEYS = frozenset(
    {
        "plan_id",
        "approved_action_ids",
        "approved_actions",
        "max_updates",
        "tool_name",
        "principal_kind",
        "operator_mode",
    }
)

_APPLY_FORBIDDEN_KEYS = frozenset(
    {
        "content",
        "path",
        "payload",
        "body",
        "note_content",
        "transcript",
        "transcript_text",
        "transcript_path",
        "target_path",
    }
)


def _reject_unknown(keys: frozenset[str], kwargs: dict[str, Any]) -> None:
    unknown = set(kwargs) - keys
    if unknown:
        raise ObsidianMcpToolError("unknown_argument", f"unsupported arguments: {sorted(unknown)}")


def normalize_transcript_kwargs(**kwargs: Any) -> dict[str, Any]:
    _reject_unknown(_TRANSCRIPT_KEYS, kwargs)
    out = dict(kwargs)
    if out.get("transcript") is None and out.get("transcript_text") is not None:
        out["transcript"] = out.pop("transcript_text")
    else:
        out.pop("transcript_text", None)
    return out


def normalize_plan_kwargs(**kwargs: Any) -> dict[str, Any]:
    _reject_unknown(_PLAN_KEYS, kwargs)
    out = dict(kwargs)
    if out.get("transcript") is None and out.get("transcript_text") is not None:
        out["transcript"] = out.pop("transcript_text")
    else:
        out.pop("transcript_text", None)
    return out


def normalize_topic_plan_kwargs(**kwargs: Any) -> dict[str, Any]:
    _reject_unknown(_TOPIC_PLAN_KEYS, kwargs)
    out = dict(kwargs)
    if out.get("transcript") is None and out.get("transcript_text") is not None:
        out["transcript"] = out.pop("transcript_text")
    else:
        out.pop("transcript_text", None)
    return out


def normalize_apply_kwargs(**kwargs: Any) -> dict[str, Any]:
    forbidden = set(kwargs) & _APPLY_FORBIDDEN_KEYS
    if forbidden:
        raise ObsidianMcpToolError(
            "unknown_argument",
            f"apply-time content injection not allowed: {sorted(forbidden)}",
        )
    _reject_unknown(_APPLY_KEYS, kwargs)
    out = dict(kwargs)
    if out.get("approved_action_ids") is None and out.get("approved_actions") is not None:
        out["approved_action_ids"] = out.pop("approved_actions")
    else:
        out.pop("approved_actions", None)
    return out
