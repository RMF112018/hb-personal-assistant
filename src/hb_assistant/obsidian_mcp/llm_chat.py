"""Orchestration for LLM chat memory MCP tools."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import llm_chat_plan_store, pathsafe
from .config import ObsidianMcpConfig
from .llm_chat_args import (
    normalize_apply_kwargs,
    normalize_plan_kwargs,
    normalize_topic_plan_kwargs,
    normalize_transcript_kwargs,
)
from .llm_chat_classify import classification_summary, classify_session
from .llm_chat_extract import (
    extract_action_items,
    extract_decisions,
    extract_memory,
    summarize_text,
)
from .llm_chat_models import LlmChatClassification, LlmChatSource
from .llm_chat_redaction import ingest_text
from .llm_chat_templates import (
    render_session_note,
    select_template,
    session_note_path,
)
from .mutations import create_note, patch_note, sha256_file, sha256_text
from .tools import ObsidianMcpToolError, read_file, resolve_safe_path
from .tools import _iter_search_files, _score

_LOG = logging.getLogger(__name__)

_PREVIEW_CHARS = 240
_DEV_DOMAINS = {"software_dev", "construction_project_management"}
_LINK_SEARCH_DEFAULT_LIMIT = 5
_LINK_SEARCH_MAX_LIMIT = 10
_LINK_SEARCH_MAX_QUERY_TERMS = 5
_LINK_SEARCH_MAX_FILES_SCANNED = 150
_LINK_SEARCH_READ_CHARS_CAP = 4096


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _preview(text: str) -> str:
    flat = " ".join(text.split())
    return flat[:_PREVIEW_CHARS]


def _log_phase(phase: str, *, plan_id: str | None = None, elapsed_ms: int | None = None) -> None:
    extra: dict[str, Any] = {}
    if plan_id:
        extra["plan_id"] = plan_id
    if elapsed_ms is not None:
        extra["elapsed_ms"] = elapsed_ms
    _LOG.info(f"llm_chat.{phase}", extra=extra)


def _log_tool(tool: str, phase: str, *, plan_id: str | None = None, arg_size: int | None = None, elapsed_ms: int | None = None, error: str | None = None) -> None:
    payload: dict[str, Any] = {"tool": tool, "phase": phase}
    if plan_id:
        payload["plan_id"] = plan_id
    if arg_size is not None:
        payload["arg_size"] = arg_size
    if elapsed_ms is not None:
        payload["elapsed_ms"] = elapsed_ms
    if error:
        payload["error"] = error
        _LOG.warning("llm_chat_tool", extra=payload)
    else:
        _LOG.info("llm_chat_tool", extra=payload)


def _ensure_enabled(config: ObsidianMcpConfig) -> None:
    if not config.llm_chat_enabled:
        raise ObsidianMcpToolError("llm_chat_disabled")


def _load_transcript(
    config: ObsidianMcpConfig,
    *,
    transcript: str | None = None,
    transcript_path: str | None = None,
    operator_mode: bool = False,
) -> tuple[str, str | None]:
    if transcript_path:
        result = read_file(config, path=transcript_path, operator_mode=operator_mode)
        content = str(result.get("content") or "")
        return content, transcript_path
    if transcript:
        return transcript, None
    raise ObsidianMcpToolError("transcript_required")


def _ingest_raw(
    config: ObsidianMcpConfig,
    args: dict[str, Any],
) -> dict[str, Any]:
    raw, path = _load_transcript(
        config,
        transcript=args.get("transcript"),
        transcript_path=args.get("transcript_path"),
        operator_mode=bool(args.get("operator_mode", False)),
    )
    limit = args.get("max_chars") or config.llm_chat_max_transcript_chars
    redact = args.get("redact", True)
    if redact is None:
        redact = True
    result = ingest_text(raw, max_chars=limit, redact=bool(redact))
    source = LlmChatSource(
        kind="vault_path" if path else "inline",
        path=path,
        hash=sha256_text(result.text),
        char_count=result.char_count,
        truncated=result.truncated,
        redaction_count=result.redaction_count,
    )
    payload: dict[str, Any] = {
        "text": result.text,
        "source": source.to_dict(),
        "truncated": result.truncated,
        "redaction_count": result.redaction_count,
        "persist_raw_transcript": config.llm_chat_persist_raw_transcript,
    }
    if not config.llm_chat_persist_raw_transcript:
        payload["note"] = "raw transcript is not persisted by default"
    return payload


def _apply_classification_overrides(
    classification: LlmChatClassification,
    text: str,
    args: dict[str, Any],
) -> LlmChatClassification:
    routing_hint = str(args.get("routing_hint") or "").strip()
    classify_text = f"{routing_hint}\n{text}" if routing_hint else text
    if routing_hint and not args.get("topic_domain"):
        boosted = classify_session(classify_text, credential_redacted=classification.sensitivity == "credential_risk")
        classification = boosted

    if args.get("topic_domain"):
        classification.primary_domain = str(args["topic_domain"])
        classification.confidence = max(classification.confidence, 0.9)
    if args.get("knowledge_type"):
        classification.knowledge_type = str(args["knowledge_type"])
    if args.get("sensitivity"):
        classification.sensitivity = str(args["sensitivity"])
    return classification


def _collect_hints(args: dict[str, Any]) -> dict[str, str]:
    hints: dict[str, str] = {}
    for key in (
        "project_hint",
        "workstream_hint",
        "topic_hint",
        "people_hint",
        "location_hint",
        "source_context_hint",
        "routing_hint",
    ):
        value = args.get(key)
        if value:
            hints[key] = str(value)
    return hints


def llm_chat_ingest(config: ObsidianMcpConfig, **kwargs: Any) -> dict[str, Any]:
    _ensure_enabled(config)
    args = normalize_transcript_kwargs(**kwargs)
    started = time.monotonic()
    _log_tool("llm_chat_ingest", "tool_start", arg_size=len(str(args.get("transcript") or "")))
    try:
        return _ingest_raw(config, args)
    except ObsidianMcpToolError:
        raise
    except Exception as exc:
        _log_tool("llm_chat_ingest", "tool_error", error=type(exc).__name__)
        raise ObsidianMcpToolError("ingest_failed") from exc
    finally:
        _log_tool("llm_chat_ingest", "tool_end", elapsed_ms=int((time.monotonic() - started) * 1000))


def llm_chat_classify(config: ObsidianMcpConfig, **kwargs: Any) -> dict[str, Any]:
    _ensure_enabled(config)
    args = normalize_transcript_kwargs(**kwargs)
    ingested = _ingest_raw(config, args)
    classification = classify_session(
        ingested["text"],
        credential_redacted=ingested["redaction_count"] > 0,
    )
    return {"classification": classification.to_dict(), "source": ingested["source"]}


def llm_chat_summarize(config: ObsidianMcpConfig, **kwargs: Any) -> dict[str, Any]:
    _ensure_enabled(config)
    args = normalize_transcript_kwargs(**kwargs)
    ingested = _ingest_raw(config, args)
    return {"summary": summarize_text(ingested["text"])}


def llm_chat_extract_decisions(config: ObsidianMcpConfig, **kwargs: Any) -> dict[str, Any]:
    _ensure_enabled(config)
    args = normalize_transcript_kwargs(**kwargs)
    ingested = _ingest_raw(config, args)
    return {"decisions": extract_decisions(ingested["text"])}


def llm_chat_extract_action_items(config: ObsidianMcpConfig, **kwargs: Any) -> dict[str, Any]:
    _ensure_enabled(config)
    args = normalize_transcript_kwargs(**kwargs)
    ingested = _ingest_raw(config, args)
    return {"action_items": extract_action_items(ingested["text"])}


def llm_chat_select_template(config: ObsidianMcpConfig, **kwargs: Any) -> dict[str, Any]:
    _ensure_enabled(config)
    args = normalize_transcript_kwargs(**kwargs)
    ingested = _ingest_raw(config, args)
    classification = classify_session(ingested["text"], credential_redacted=ingested["redaction_count"] > 0)
    classification = _apply_classification_overrides(classification, ingested["text"], args)
    selection = select_template(
        config,
        classification,
        template_mode=str(args.get("template_mode") or "auto"),
        target_folder=args.get("target_folder"),
    )
    return {"template_selection": selection.to_dict(), "classification": classification.to_dict()}


def _bounded_query_terms(*parts: str) -> list[str]:
    terms: list[str] = []
    for part in parts:
        for token in re.split(r"\W+", part.lower()):
            if len(token) < 2 or token in terms:
                continue
            terms.append(token)
            if len(terms) >= _LINK_SEARCH_MAX_QUERY_TERMS:
                return terms
    return terms


def _stem_score(path: Path, terms: list[str]) -> float:
    if not terms:
        return 0.0
    stem = path.stem.lower()
    score = 0.0
    for term in terms:
        if term in stem:
            score += 3.0
    return score


def _bounded_vault_link_search(
    config: ObsidianMcpConfig,
    query_terms: list[str],
    *,
    limit: int,
    operator_mode: bool = False,
) -> dict[str, Any]:
    query = " ".join(query_terms)
    if not query_terms:
        return {"suggested_links": [], "query": query, "warnings": []}

    root = Path(config.vault_root).expanduser().resolve()
    read_cap = min(_LINK_SEARCH_READ_CHARS_CAP, config.max_result_chars)
    result_limit = min(max(1, limit), _LINK_SEARCH_MAX_LIMIT)
    warnings: list[str] = []

    try:
        candidates = _iter_search_files(config, None, ["md"], operator_mode=operator_mode)
    except ObsidianMcpToolError:
        return {"suggested_links": [], "query": query, "warnings": ["related_note_search_failed"]}

    stem_ranked: list[tuple[float, Path]] = []
    scanned = 0
    for path in candidates:
        scanned += 1
        if scanned > _LINK_SEARCH_MAX_FILES_SCANNED:
            break
        stem_ranked.append((_stem_score(path, query_terms), path))

    stem_ranked.sort(key=lambda item: (-item[0], item[1].as_posix().lower()))
    read_candidates = [path for score, path in stem_ranked if score > 0][: result_limit * 3]
    if not read_candidates:
        read_candidates = [path for _, path in stem_ranked[: result_limit * 3]]

    scored: list[tuple[float, str]] = []
    for path in read_candidates:
        try:
            rel = path.resolve().relative_to(root).as_posix()
            read = read_file(config, path=rel, max_chars=read_cap, operator_mode=operator_mode)
            content = str(read.get("content") or "")
            score = _score(content, path, query)
            if score > 0:
                scored.append((score, rel))
        except (TimeoutError, OSError, UnicodeError):
            warnings.append("related_note_search_failed")
            continue
        except ObsidianMcpToolError:
            continue

    scored.sort(key=lambda item: (-item[0], item[1]))
    links = [rel for _, rel in scored[:result_limit]]
    return {"suggested_links": links, "query": query, "warnings": warnings}


def llm_chat_link_existing_notes(config: ObsidianMcpConfig, **kwargs: Any) -> dict[str, Any]:
    _ensure_enabled(config)
    args = normalize_transcript_kwargs(**kwargs)
    requested_limit = int(args.get("limit", _LINK_SEARCH_DEFAULT_LIMIT))
    limit = min(max(1, requested_limit), _LINK_SEARCH_MAX_LIMIT)
    ingested = _ingest_raw(config, args)
    classification = classify_session(ingested["text"])
    domain_query = classification.primary_domain.replace("_", " ")
    query_terms = _bounded_query_terms(domain_query)
    try:
        result = _bounded_vault_link_search(
            config,
            query_terms,
            limit=limit,
            operator_mode=bool(args.get("operator_mode", False)),
        )
    except (TimeoutError, OSError, UnicodeError):
        return {"suggested_links": [], "query": domain_query, "warnings": ["related_note_search_failed"]}
    return result


def _redaction_summary(redaction_count: int, truncated: bool) -> str:
    parts: list[str] = []
    if redaction_count:
        parts.append(f"{redaction_count} secret pattern(s) redacted")
    if truncated:
        parts.append("transcript truncated to max_chars")
    return "; ".join(parts) if parts else "none"


def llm_chat_to_note_plan(config: ObsidianMcpConfig, **kwargs: Any) -> dict[str, Any]:
    _ensure_enabled(config)
    args = normalize_plan_kwargs(**kwargs)
    started = time.monotonic()

    def _elapsed_ms() -> int:
        return int((time.monotonic() - started) * 1000)

    plan_id = llm_chat_plan_store.new_plan_id()
    _log_phase("plan_start", plan_id=plan_id, elapsed_ms=_elapsed_ms())
    warnings: list[str] = []

    ingested = _ingest_raw(config, args)
    _log_phase("ingest_end", plan_id=plan_id, elapsed_ms=_elapsed_ms())
    text = ingested["text"]
    classification = classify_session(text, credential_redacted=ingested["redaction_count"] > 0)
    classification = _apply_classification_overrides(classification, text, args)
    _log_phase("classify_end", plan_id=plan_id, elapsed_ms=_elapsed_ms())
    extraction = extract_memory(text, classification)
    if args.get("conversation_title"):
        extraction.conversation_title = str(args["conversation_title"])
    _log_phase("extract_end", plan_id=plan_id, elapsed_ms=_elapsed_ms())

    selection = select_template(
        config,
        classification,
        template_mode=str(args.get("template_mode") or "auto"),
        target_folder=args.get("target_folder"),
    )
    _log_phase("template_end", plan_id=plan_id, elapsed_ms=_elapsed_ms())

    links = list(args.get("related_notes") or [])
    candidate_links: list[str] = []
    if bool(args.get("link_existing_notes", False)):
        _log_phase("related_links_start", plan_id=plan_id, elapsed_ms=_elapsed_ms())
        try:
            link_result = llm_chat_link_existing_notes(
                config,
                transcript=text,
                operator_mode=args.get("operator_mode", False),
            )
            candidate_links = list(link_result.get("suggested_links") or [])
            for item in candidate_links:
                if item not in links:
                    links.append(item)
            for item in link_result.get("warnings") or []:
                if item not in warnings:
                    warnings.append(item)
        except (TimeoutError, OSError, UnicodeError):
            warnings.append("related_note_search_failed")
        _log_phase("related_links_end", elapsed_ms=_elapsed_ms(), plan_id=plan_id)
    else:
        _log_phase("related_links_skipped", plan_id=plan_id, elapsed_ms=_elapsed_ms())

    source = dict(ingested["source"])
    source["platform"] = str(args.get("source_platform") or "unknown")
    source["model"] = str(args.get("source_model") or "unknown")
    if args.get("include_raw_transcript"):
        source["include_raw_transcript_requested"] = True
    red_summary = _redaction_summary(ingested["redaction_count"], ingested["truncated"])
    class_summary = classification_summary(classification)
    hints = _collect_hints(args)

    include_domain_sections = args.get("include_domain_specific_sections")
    body = render_session_note(
        config,
        plan_id=plan_id,
        classification=classification,
        extraction=extraction,
        selection=selection,
        source=source,
        related_notes=links,
        redaction_summary=red_summary,
        classification_summary=class_summary,
        conversation_date=args.get("conversation_date"),
        hints=hints,
        include_domain_specific_sections=include_domain_sections,
    )
    target_path = session_note_path(selection, extraction.conversation_title)
    try:
        resolve_safe_path(config, target_path, must_exist=False)
    except ObsidianMcpToolError as exc:
        raise ObsidianMcpToolError("invalid_target_path", str(exc)) from exc

    action_id = "create_session_note"
    action = {
        "id": action_id,
        "action": "create_session_note",
        "target_path": target_path,
        "op": "create",
        "expected_sha256": None,
        "preview": _preview(body),
        "payload": body,
    }
    if include_domain_sections is False or classification.primary_domain not in _DEV_DOMAINS:
        for marker in ("Commands That Worked", "Root Cause Analysis", "Patch Plan", "Validation Steps"):
            if marker in body:
                warnings.append(f"dev_section_leak:{marker}")

    plan = {
        "plan_id": plan_id,
        "plan_kind": "session_note",
        "created_at": _now_iso(),
        "source": source,
        "classification": classification.to_dict(),
        "extraction": {k: v for k, v in extraction.to_dict().items() if k != "domain_fields"},
        "template_selection": selection.to_dict(),
        "allowed_actions": [action_id],
        "actions": [action],
        "warnings": warnings,
        "include_raw_transcript_requested": bool(args.get("include_raw_transcript")),
    }
    llm_chat_plan_store.save_plan(plan)
    _log_phase("persist_end", plan_id=plan_id, elapsed_ms=_elapsed_ms())
    _log_phase("plan_end", plan_id=plan_id, elapsed_ms=_elapsed_ms())

    return {
        "plan_id": plan_id,
        "target_path": target_path,
        "template_selection": selection.to_dict(),
        "classification": classification.to_dict(),
        "previews": [{"action_id": action_id, "target_path": target_path, "preview": action["preview"]}],
        "proposed_actions": [
            {
                "id": action_id,
                "action": "create_session_note",
                "target_path": target_path,
                "preview": action["preview"],
            }
        ],
        "warnings": warnings,
        "tags": extraction.tags,
        "related_notes": links,
        "candidate_links": candidate_links,
    }


def llm_chat_to_note_apply(config: ObsidianMcpConfig, **kwargs: Any) -> dict[str, Any]:
    _ensure_enabled(config)
    args = normalize_apply_kwargs(**kwargs)
    plan_id = str(args["plan_id"])
    approved_action_ids = args.get("approved_action_ids")
    max_updates = args.get("max_updates")
    tool_name = str(args.get("tool_name") or "llm_chat_to_note_apply")
    principal_kind = args.get("principal_kind")
    plan = llm_chat_plan_store.load_plan(plan_id)
    if plan is None:
        raise ObsidianMcpToolError("unknown_plan")

    allowed = set(plan.get("allowed_actions", []))
    approved = set(approved_action_ids or allowed)
    if approved - allowed:
        raise ObsidianMcpToolError("action_not_in_plan")

    cap = max_updates or config.llm_chat_max_plan_updates
    selected = [a for a in plan.get("actions", []) if a.get("id") in approved]
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    used = 0

    for action in selected:
        if used >= cap:
            skipped.append({"target_path": action.get("target_path"), "reason": "max_updates", "action_id": action.get("id")})
            continue
        target = str(action.get("target_path", ""))
        try:
            if action.get("op") == "create":
                result = create_note(
                    config,
                    path=target,
                    content=str(action.get("payload", "")),
                    overwrite=False,
                    caller_surface="mcp_llm_chat",
                    tool_name=tool_name,
                    principal_kind=principal_kind,
                    plan_id=plan_id,
                )
                applied.append(
                    {
                        "action_id": action.get("id"),
                        "target_path": target,
                        "op": "create",
                        "sha256": result["sha256"],
                        "backup_path": result.get("backup_path"),
                    }
                )
                used += 1
            elif action.get("op") == "patch":
                expected = str(action.get("expected_sha256", ""))
                result = patch_note(
                    config,
                    path=target,
                    content=str(action.get("payload", "")),
                    expected_sha256=expected,
                    caller_surface="mcp_llm_chat",
                    tool_name=tool_name,
                    principal_kind=principal_kind,
                    plan_id=plan_id,
                )
                applied.append(
                    {
                        "action_id": action.get("id"),
                        "target_path": target,
                        "op": "patch",
                        "sha256": result["sha256"],
                        "backup_path": result.get("backup_path"),
                    }
                )
                used += 1
        except ObsidianMcpToolError as exc:
            failed.append({"target_path": target, "reason": exc.code, "action_id": action.get("id")})

    counts = {"applied": len(applied), "skipped": len(skipped), "failed": len(failed)}
    receipt = {
        "plan_id": plan_id,
        "applied_at": _now_iso(),
        "approved_action_ids": sorted(approved),
        "max_updates": cap,
        "applied": applied,
        "skipped": skipped,
        "failed": failed,
        "counts": counts,
    }
    llm_chat_plan_store.write_receipt(plan_id, receipt)
    return {"plan_id": plan_id, "applied": applied, "skipped": skipped, "failed": failed, "counts": counts}


def llm_chat_update_topic_memory_plan(config: ObsidianMcpConfig, **kwargs: Any) -> dict[str, Any]:
    _ensure_enabled(config)
    args = normalize_topic_plan_kwargs(**kwargs)
    ingested = _ingest_raw(config, args)
    text = ingested["text"]
    classification = classify_session(text, credential_redacted=ingested["redaction_count"] > 0)
    extraction = extract_memory(text, classification)

    resolved = resolve_safe_path(config, str(args["target_path"]), must_exist=True)
    if pathsafe.path_blocked(resolved.relative, include_hidden=False):
        raise ObsidianMcpToolError("protected_path_blocked")
    existing = resolved.path.read_text(encoding="utf-8", errors="replace")
    expected_sha = sha256_file(resolved.path)

    append_block = "\n".join(
        [
            "",
            "## LLM Memory Update",
            f"- Processed: {_now_iso()}",
            "",
            extraction.executive_summary,
            "",
            extraction.decisions_or_conclusions,
            "",
            extraction.action_items,
            "",
        ]
    )
    new_body = existing.rstrip() + append_block

    plan_id = llm_chat_plan_store.new_plan_id()
    action_id = "update_topic_memory"
    action = {
        "id": action_id,
        "action": "update_topic_memory",
        "target_path": resolved.relative,
        "op": "patch",
        "expected_sha256": expected_sha,
        "preview": _preview(append_block),
        "payload": new_body,
    }
    plan = {
        "plan_id": plan_id,
        "plan_kind": "topic_memory",
        "created_at": _now_iso(),
        "source": ingested["source"],
        "classification": classification.to_dict(),
        "extraction": {k: v for k, v in extraction.to_dict().items() if k != "domain_fields"},
        "template_selection": None,
        "allowed_actions": [action_id],
        "actions": [action],
        "warnings": [],
    }
    llm_chat_plan_store.save_plan(plan)
    return {
        "plan_id": plan_id,
        "target_path": resolved.relative,
        "expected_sha256": expected_sha,
        "preview": action["preview"],
        "proposed_actions": [
            {
                "id": action_id,
                "action": "update_topic_memory",
                "target_path": resolved.relative,
                "expected_sha256": expected_sha,
                "preview": action["preview"],
            }
        ],
    }


def llm_chat_update_topic_memory_apply(config: ObsidianMcpConfig, **kwargs: Any) -> dict[str, Any]:
    args = normalize_apply_kwargs(**kwargs)
    return llm_chat_to_note_apply(config, **args)


def llm_chat_status(config: ObsidianMcpConfig) -> dict[str, Any]:
    from .llm_chat_templates import list_available_templates

    templates = list_available_templates(config)
    recent = llm_chat_plan_store.list_plans(10)
    redacted_plans = [
        {
            "plan_id": p.get("plan_id"),
            "plan_kind": p.get("plan_kind"),
            "created_at": p.get("created_at"),
            "primary_domain": (p.get("classification") or {}).get("primary_domain"),
            "action_count": len(p.get("actions", [])),
        }
        for p in recent
    ]
    return {
        "llm_chat_enabled": config.llm_chat_enabled,
        "template_dir": config.llm_chat_template_dir,
        "project_template_path": config.llm_chat_project_template_path,
        "plan_store_path": str(llm_chat_plan_store.plan_dir()),
        "plan_count": llm_chat_plan_store.plan_count(),
        "templates_found": len(templates),
        "template_names": templates,
        "raw_transcript_persistence": config.llm_chat_persist_raw_transcript,
        "redaction_enabled": True,
        "recent_plans": redacted_plans,
    }
