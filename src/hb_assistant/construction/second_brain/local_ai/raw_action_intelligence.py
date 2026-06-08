"""Phase 10A Prompt 07 — Action Intelligence from Raw Content.

Local-model extraction of actionable candidates (task, commitment, follow-up, etc.)
directly from Phase 10A raw email/calendar content (V42 raw tables / P06 packets).

- Strict ActionCandidate schema (via existing Pydantic model + extra="forbid").
- Business-contract validation that explicitly rejects generic data-cleaning,
  pure analysis, or hallucinated "process the data" outputs that are not tied to
  concrete project deliverables.
- Retry + self-repair on bad JSON or business validation failures (append
  repair instruction with the error; up to 3 attempts total).
- Persists to V41 action tables (task_candidates / commitment_candidates) +
  candidate_source_refs, carrying bounded raw source excerpts (evidence_redacted)
  linked to the originating raw row (email_message_raw_content or
  calendar_event_raw_content).
- Fully mockable via mock_output (for hermetic tests / CLI --mock-output).
- Advisory only: never auto-accepts; recommended_next_action and review_status
  drive human review.

Entry points (additive):
  extract_action_candidates_from_raw(
      *,
      raw_email_packet: dict | None = None,
      raw_calendar_packet: dict | None = None,
      project_key: str | None = None,
      store: ConstructionStore | None = None,
      mock_output: str | None = None,
      max_items: int = 20,
  ) -> dict[str, Any]
    Returns a report with:
      "produced": int, "accepted": int, "rejected": int, "persisted": int,
      "candidates": list[ActionCandidate],
      "rejections": list[dict]  # {reason, item or raw_output}

The prompt forces the model to emit ONLY JSON (array of candidate objects) matching
the Phase10 action candidate output schema. No prose.

Raw excerpts used in prompts and persisted evidence are bounded (never full bodies
outside the V42 raw tables themselves).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from hb_assistant.construction.classification.client import (
    OllamaChatClient,
    OllamaUnavailable,
)
from hb_assistant.construction.second_brain.local_ai.models import ActionCandidate
from hb_assistant.construction.store import ConstructionStore

STRICT_ACTION_SYSTEM = (
    "You are a precise, grounded action extraction engine for construction projects.\n"
    "You will be shown bounded raw excerpts from email threads or calendar events.\n"
    "Output ONE JSON object with a top-level `candidates` array of ActionCandidate objects.\n"
    "For no actions, output exactly:\n"
    '{"candidates":[]}\n'
    "Each candidate object MUST exactly match the Phase 10 ActionCandidate schema (field list below).\n"
    "Output NOTHING except the single JSON object. No markdown, no explanations, no prose.\n\n"
    "Required/important fields (exact names and types):\n"
    "- candidate_type: one of task|commitment|decision|question|meeting_prep|risk_signal|relationship\n"
    "- title: short, concrete, max 240 chars\n"
    "- project_key: string or null\n"
    "- assignee (for tasks) or commitment_actor_class (for commitments): user|other|unknown\n"
    "- due_at: ISO string or null\n"
    "- urgency: low|normal|high|critical\n"
    "- waiting_state: waiting_on_me|waiting_on_others|unknown|not_applicable\n"
    "- source_refs: array of at least 1 non-empty string identifiers (hashes or stable row refs from input)\n"
    "- confidence: number 0.0-1.0\n"
    "- reason: short grounded justification, max 1000 chars. Must cite concrete signals from the excerpts.\n"
    "- safety_category: normal|contract|legal|financial|payment|claim|entitlement|schedule|safety\n"
    "- recommended_next_action: review|accept|snooze|ignore|draft_followup|prepare_meeting|prepare_packet\n"
    "- model_name, model_profile_id, prompt_template_version, input_window_hash: strings or null (use null if unknown)\n"
    "- review_status: pending (always start as pending)\n"
    "- external_action_requires_approval: true (always)\n\n"
    "Business rules you MUST follow:\n"
    "- Only emit concrete, project-deliverable actions (e.g. 'Submit revised RFI sketch by EOD', 'Confirm vendor commitment for material delivery on 2026-06-12').\n"
    "- NEVER emit generic data-cleaning, data-analysis, 'normalize the data', 'analyze trends', 'clean up the spreadsheet', 'process the information', or similar non-actionable meta-work.\n"
    "- If the content only contains analysis requests without a clear deliverable task or commitment, output {\"candidates\":[]}.\n"
    "- source_refs must be taken from the provided excerpts (e.g. message ids, conversation hashes, event ids).\n"
    "- reason must be directly supported by the raw excerpt text shown.\n\n"
    "If the input contains no actionable project work, output exactly {\"candidates\":[]}.\n"
)

_MAX_EXCERPT_CHARS = 1200
_MAX_ITEMS_PER_CALL = 50


def _truncate(s: Optional[str], n: int = _MAX_EXCERPT_CHARS) -> Optional[str]:
    if not s:
        return None
    s = str(s)
    if len(s) <= n:
        return s
    return s[:n] + "…[truncated]"


def _build_raw_excerpts(
    *,
    raw_email_packet: Optional[dict[str, Any]],
    raw_calendar_packet: Optional[dict[str, Any]],
    project_key: Optional[str],
    store: Optional[ConstructionStore],
    max_items: int,
    source: str = "both",
) -> list[dict[str, Any]]:
    """Collect bounded raw excerpts + stable source identifiers.

    Prefers passed packets (P06 shape). Falls back to loading recent raw rows
    for the project via the store (P05 list raw surfaces). ``source`` ("email"|"calendar"|"both")
    restricts which families are considered, for both the packet path and the store fallback.
    """
    want_email = source in ("email", "both")
    want_calendar = source in ("calendar", "both")
    excerpts: list[dict[str, Any]] = []

    if raw_email_packet and want_email:
        for th in (raw_email_packet.get("content") or {}).get("threads") or []:
            for m in (th.get("messages") or [])[:max_items]:
                excerpts.append(
                    {
                        "source_family": "email_message_raw_content",
                        "source_ref": m.get("id") or th.get("thread_ref"),
                        "subject": m.get("subject") or th.get("thread_subject"),
                        "body_text": _truncate(m.get("body_text")),
                        "from_name": m.get("from_name"),
                        "to_recipients": m.get("to_recipients") or [],
                        "sent_at_utc": m.get("sent_at_utc"),
                    }
                )
                if len(excerpts) >= max_items:
                    break
            if len(excerpts) >= max_items:
                break

    if raw_calendar_packet and want_calendar and len(excerpts) < max_items:
        for ev in (raw_calendar_packet.get("content") or {}).get("events") or []:
            excerpts.append(
                {
                    "source_family": "calendar_event_raw_content",
                    "source_ref": ev.get("event_index_id"),
                    "subject": ev.get("subject"),
                    "body_text": _truncate(ev.get("body_text")),
                    "location": ev.get("location"),
                    "organizer": ev.get("organizer"),
                    "attendees": ev.get("attendees") or [],
                    "join_url": ev.get("join_url"),
                    "start": ev.get("start"),
                    "end": ev.get("end"),
                }
            )
            if len(excerpts) >= max_items:
                break

    if not excerpts and project_key and store is not None:
        # Fallback: load recent raw rows directly
        try:
            raw_msgs = (
                store.list_email_message_raw_content(project_key=project_key, limit=max_items)
                if want_email
                else []
            )
            for m in raw_msgs:
                excerpts.append(
                    {
                        "source_family": "email_message_raw_content",
                        "source_ref": m.get("message_id_hash"),
                        "subject": m.get("subject"),
                        "body_text": _truncate(m.get("body_text")),
                        "from_name": m.get("from_name"),
                        "to_recipients": m.get("to_recipients") or [],
                        "sent_at_utc": m.get("sent_at_utc"),
                    }
                )
                if len(excerpts) >= max_items:
                    break
        except Exception:
            pass
        if want_calendar and len(excerpts) < max_items:
            try:
                raw_evs = store.list_calendar_event_raw_content(
                    project_key=project_key, limit=max_items
                )
                for e in raw_evs:
                    excerpts.append(
                        {
                            "source_family": "calendar_event_raw_content",
                            "source_ref": e.get("event_index_id") or e.get("raw_calendar_event_id"),
                            "subject": e.get("subject"),
                            "body_text": _truncate(e.get("body_text")),
                            "location": e.get("location_display"),
                            "organizer": {
                                "name": e.get("organizer_name"),
                                "email": e.get("organizer_email"),
                            },
                            "attendees": e.get("attendees") or [],
                            "join_url": e.get("join_url"),
                            "start": e.get("start_datetime_utc"),
                            "end": e.get("end_datetime_utc"),
                        }
                    )
                    if len(excerpts) >= max_items:
                        break
            except Exception:
                pass

    return excerpts[:max_items]


def _build_prompt(excerpts: list[dict[str, Any]]) -> str:
    lines = [
        "RAW CONTENT EXCERPTS (bounded; use only these signals):",
    ]
    for i, ex in enumerate(excerpts, 1):
        fam = ex.get("source_family", "unknown")
        ref = ex.get("source_ref", f"item-{i}")
        subj = ex.get("subject") or "(no subject)"
        body = ex.get("body_text") or ""
        lines.append(f"--- excerpt {i} ({fam} ref={ref}) ---")
        lines.append(f"subject: {subj}")
        if body:
            lines.append(f"body: {body}")
        if ex.get("from_name"):
            lines.append(f"from: {ex.get('from_name')}")
        if ex.get("location"):
            lines.append(f"location: {ex.get('location')}")
        if ex.get("start"):
            lines.append(f"when: {ex.get('start')} - {ex.get('end')}")
        lines.append("")
    lines.append(
        "TASK: Output ONE JSON object with a top-level `candidates` array (use {\"candidates\":[]} if "
        "none). Follow the schema and business rules in the system prompt exactly.\n"
        "Example shape (placeholder values; use real source_refs from the excerpts above):\n"
        '{"candidates":[{"candidate_type":"task","title":"Submit revised RFI sketch by Friday",'
        '"project_key":null,"assignee":"user","due_at":null,"urgency":"normal",'
        '"waiting_state":"waiting_on_me","source_refs":["<ref-from-excerpt>"],"confidence":0.8,'
        '"reason":"Sender asks to submit the revised sketch.","safety_category":"normal",'
        '"recommended_next_action":"review","review_status":"pending",'
        '"external_action_requires_approval":true}]}'
    )
    return "\n".join(lines)


def _validate_business_contract(candidate: ActionCandidate) -> Optional[str]:
    """Return rejection reason string if the candidate is a generic data-clean/analysis hallucination.

    Otherwise return None (accept).
    """
    text = " ".join(
        filter(
            None,
            [
                (candidate.title or "").lower(),
                (candidate.reason or "").lower(),
            ],
        )
    )
    generic_patterns = (
        "clean the data",
        "normalize the data",
        "data cleaning",
        "data analysis",
        "analyze the data",
        "perform data analysis",
        "summarize trends",
        "clean up the spreadsheet",
        "process the information",
        "extract fields for analysis",
        "data quality",
        "standardize the data",
    )
    for pat in generic_patterns:
        if pat in text:
            return f"generic_data_work: contains forbidden pattern '{pat}'"
    # Must be tied to a concrete deliverable-ish title for task/commitment
    if (
        candidate.candidate_type in ("task", "commitment")
        and len((candidate.title or "").strip()) < 8
    ):
        return "title_too_vague_for_action"
    return None


def _run_with_retry_repair(
    *,
    client: Optional[OllamaChatClient],
    prompt: str,
    mock_output: Optional[str],
    max_attempts: int = 3,
) -> tuple[Optional[str], Optional[str], bool]:
    """Call the model (or use mock). On parse/business failure, repair up to max_attempts.

    Returns ``(raw_model_text_or_None, error_class_redacted_or_None, is_timeout)``. The error class is a
    safe redacted token: the OllamaUnavailable category code (e.g. ``ollama_request_failed``) or the
    exception *type name only* — never the message/body/URL/token.
    """
    current_prompt = prompt
    error_class: Optional[str] = None
    is_timeout = False
    for attempt in range(1, max_attempts + 1):
        if mock_output is not None:
            return mock_output, None, False
        if client is None:
            return None, None, False
        try:
            raw = client.generate_json(system=STRICT_ACTION_SYSTEM, prompt=current_prompt)
            return raw, None, False
        except Exception as exc:  # Ollama errors etc.
            # OllamaUnavailable carries a safe category code (no body/URL/token); otherwise type name.
            error_class = str(exc) if isinstance(exc, OllamaUnavailable) else type(exc).__name__
            is_timeout = "timeout" in str(exc).lower()
            if attempt == max_attempts:
                return None, error_class, is_timeout
            current_prompt = (
                prompt
                + f"\n\nPREVIOUS ATTEMPT FAILED (attempt {attempt}, {error_class}). "
                + "Return ONLY a JSON object with top-level key `candidates` containing an array "
                + "matching the Phase 10 ActionCandidate schema exactly. No other text."
            )
    return None, error_class, is_timeout


def _diagnostic_reason(
    *,
    client: Optional[OllamaChatClient],
    mock_output: Optional[str],
    error_class: Optional[str],
    is_timeout: bool,
    produced: int,
    accepted: int,
    last_parse_error: Optional[str],
    envelope_invalid: bool = False,
    parsed_ok: bool = False,
) -> Optional[str]:
    """Classify a run into one safe diagnostic reason (or None on clean success).

    ``no_candidates`` = a valid object/array envelope with zero candidates (the model ran, found
    nothing). ``invalid_output_envelope`` = a JSON object without a usable candidates/items list.
    ``empty_model_output`` is reserved for truly empty/None raw output (no JSON parsed at all).
    """
    if client is None and mock_output is None:
        return "no_client_constructed"
    if is_timeout or (error_class and "timeout" in error_class.lower()):
        return "model_timeout"
    if error_class:
        return "ollama_unreachable"
    if produced > 0 and accepted == 0:
        return "schema_rejected_output"
    if parsed_ok and produced == 0:
        return "no_candidates"
    if envelope_invalid:
        return "invalid_output_envelope"
    if last_parse_error and "json" in last_parse_error.lower():
        return "invalid_json_output"
    if not parsed_ok:
        return "empty_model_output"
    return None


def _build_diagnostics(
    *,
    reason: Optional[str],
    client: Optional[OllamaChatClient],
    mock_output: Optional[str],
    prompt: str,
    excerpts: list[dict[str, Any]],
    error_class: Optional[str],
    parse_meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Safe diagnostics: model/profile, char counts, reachability bool, redacted error class + reason.

    ``parse_meta`` carries safe shape facts (root_type / has_*_key / response_char_count /
    parsed_candidate_count) — never any raw response body, prompt, URL, token, or source content.
    """
    if mock_output is not None:
        model_name: Optional[str] = "mock"
    elif client is not None:
        model_name = getattr(client, "model", None)
    else:
        model_name = None
    if reason in ("ollama_unreachable", "model_timeout"):
        endpoint_reachable: Optional[bool] = False
    elif client is not None and mock_output is None:
        endpoint_reachable = True
    else:
        endpoint_reachable = None
    packet_char_estimate = sum(
        len(str(ex.get("body_text") or "")) + len(str(ex.get("subject") or "")) for ex in excerpts
    )
    meta = parse_meta or {}
    return {
        "model_name": model_name,
        "profile_id": None,
        "prompt_char_count": len(prompt),
        "packet_char_estimate": packet_char_estimate,
        "endpoint_reachable": endpoint_reachable,
        "error_class_redacted": error_class,
        "reason": reason,
        "root_type": meta.get("root_type"),
        "has_candidates_key": meta.get("has_candidates_key", False),
        "has_items_key": meta.get("has_items_key", False),
        "response_char_count": meta.get("response_char_count", 0),
        "parsed_candidate_count": meta.get("parsed_candidate_count", 0),
    }


def extract_action_candidates_from_raw(
    *,
    raw_email_packet: Optional[dict[str, Any]] = None,
    raw_calendar_packet: Optional[dict[str, Any]] = None,
    project_key: Optional[str] = None,
    store: Optional[ConstructionStore] = None,
    mock_output: Optional[str] = None,
    max_items: int = 20,
    client: Optional[OllamaChatClient] = None,
    dry_run: bool = True,
    source: str = "both",
    source_family_map: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Main entry point for P07.

    Loads (or accepts) raw content (restricted by ``source``), builds bounded prompt, runs model
    (or mock), strict + business validation with retry/repair, and — only when ``dry_run`` is False —
    persists accepted candidates + source refs. Dry-run (the default) performs **zero** writes and
    reports ``would_persist`` instead. Returns a report.
    """
    if source not in ("email", "calendar", "both"):
        raise ValueError(f"unknown source {source!r}")
    s = store or ConstructionStore()

    excerpts = _build_raw_excerpts(
        raw_email_packet=raw_email_packet,
        raw_calendar_packet=raw_calendar_packet,
        project_key=project_key,
        store=s,
        max_items=min(max_items, _MAX_ITEMS_PER_CALL),
        source=source,
    )

    if not excerpts:
        return {
            "produced": 0,
            "accepted": 0,
            "rejected": 0,
            "persisted": 0,
            "would_persist": 0,
            "dry_run": dry_run,
            "source": source,
            "candidates": [],
            "rejections": [],
            "note": "no raw content available for the given project/packets/source",
        }

    prompt = _build_prompt(excerpts)

    # Authoritative source_family per ref: packet source_refs (thread/message/event) override the
    # excerpt-derived families. No string guessing, no calendar fallback.
    excerpt_family = {
        str(ex["source_ref"]): str(ex.get("source_family") or "")
        for ex in excerpts
        if ex.get("source_ref")
    }
    known_family: dict[str, str] = {**excerpt_family, **(source_family_map or {})}

    # No model was actually called — never report "model returned no output".
    if client is None and mock_output is None:
        return {
            "produced": 0, "accepted": 0, "rejected": 0, "persisted": 0, "would_persist": 0,
            "dry_run": dry_run, "source": source, "candidates": [],
            "rejections": [{"reason": "no_client_constructed"}],
            "note": "no_model_client",
            "diagnostics": _build_diagnostics(
                reason="no_client_constructed", client=client, mock_output=mock_output,
                prompt=prompt, excerpts=excerpts, error_class=None,
            ),
        }

    # Try up to N times (the repair helper handles appending instructions)
    raw_json: Optional[str] = None
    last_parse_error: Optional[str] = None
    error_class: Optional[str] = None
    is_timeout = False
    parsed_ok = False  # a valid object/array envelope was parsed (even if zero candidates)
    envelope_invalid = False  # a JSON object without a usable candidates/items list was seen
    parse_meta: dict[str, Any] = {
        "root_type": None, "has_candidates_key": False, "has_items_key": False,
        "response_char_count": 0, "parsed_candidate_count": 0,
    }
    final_report: Optional[dict[str, Any]] = None
    for attempt in range(3):
        raw_json, err, tmo = _run_with_retry_repair(
            client=client,
            prompt=prompt,
            mock_output=mock_output
            if attempt == 0
            else None,  # mock only on first; tests control via outer
            max_attempts=1,  # single shot per outer attempt; repair is in the helper
        )
        error_class = err or error_class
        is_timeout = is_timeout or tmo
        if not raw_json:
            # Don't clobber a prior invalid-JSON error from an earlier attempt.
            if last_parse_error is None:
                last_parse_error = "model returned no output"
            continue
        try:
            root = json.loads(raw_json)
            # Object-root is primary: {"candidates": [...]}; raw arrays stay backward compatible.
            parse_meta = {
                "root_type": "array" if isinstance(root, list)
                else "object" if isinstance(root, dict) else type(root).__name__,
                "has_candidates_key": isinstance(root, dict) and "candidates" in root,
                "has_items_key": isinstance(root, dict) and "items" in root,
                "response_char_count": len(raw_json),
                "parsed_candidate_count": 0,
            }
            if isinstance(root, list):
                parsed = root
            elif isinstance(root, dict) and isinstance(root.get("candidates"), list):
                parsed = root["candidates"]
            elif isinstance(root, dict) and isinstance(root.get("items"), list):
                parsed = root["items"]
            else:
                # Object without a usable candidates/items list (e.g. {}) — malformed envelope.
                envelope_invalid = True
                last_parse_error = last_parse_error or "invalid_output_envelope"
                prompt = (
                    prompt
                    + "\n\nPREVIOUS OUTPUT WAS A JSON OBJECT WITHOUT A `candidates` ARRAY. "
                    + "Return ONLY a JSON object with top-level key `candidates` containing an array."
                )
                continue
            parsed_ok = True
            parse_meta["parsed_candidate_count"] = len(parsed)
            candidates: list[ActionCandidate] = []
            rejections: list[dict[str, Any]] = []
            for item in parsed:
                try:
                    cand = ActionCandidate.model_validate(item)
                    rej = _validate_business_contract(cand)
                    if rej:
                        rejections.append({"reason": rej, "candidate": cand.model_dump()})
                        continue
                    # Every cited source_ref must resolve to a real packet/excerpt ref + family.
                    unknown = [r for r in cand.source_refs if str(r) not in known_family]
                    if unknown:
                        rejections.append(
                            {"reason": "source_ref_not_in_packet", "candidate": cand.model_dump()}
                        )
                        continue
                    candidates.append(cand)
                except Exception as ve:  # validation or business
                    rejections.append(
                        {"reason": f"schema_or_business_validation_error: {ve}", "raw_item": item}
                    )
            # Persist accepted candidates — ONLY on apply (dry-run performs zero writes).
            persistable = [c for c in candidates if c.candidate_type in ("task", "commitment")]
            persisted = 0
            seen_stable_keys: set[str] = set()
            if not dry_run:
                for cand in persistable:
                    try:
                        # Deterministic SHA-256 keys → idempotent re-apply (same source refs dedupe to
                        # one candidate row + one source-ref row, updated in place via ON CONFLICT).
                        refs_key = hashlib.sha256(
                            "|".join(sorted(cand.source_refs)).encode("utf-8")
                        ).hexdigest()[:16]
                        stable_key = f"raw-{cand.candidate_type}:{refs_key}"
                        # Within a run, the first candidate for a (type, source-refs) set wins; later
                        # duplicates are skipped (deterministic, order-stable) rather than overwriting.
                        if stable_key in seen_stable_keys:
                            continue
                        seen_stable_keys.add(stable_key)
                        candidate_id = hashlib.sha256(
                            f"{cand.candidate_type}|{'|'.join(sorted(cand.source_refs))}".encode()
                        ).hexdigest()[:24]
                        common: dict[str, Any] = {
                            "candidate_id": candidate_id,
                            "title_redacted": cand.title,
                            "project_key": cand.project_key or project_key,
                            "due_at_utc": cand.due_at,
                            "urgency": cand.urgency,
                            "waiting_state": cand.waiting_state,
                            "safety_category": cand.safety_category,
                            "confidence": cand.confidence,
                            "reason_redacted": cand.reason,
                            "recommended_next_action": cand.recommended_next_action,
                            "review_status": cand.review_status,
                            "model_profile_id": cand.model_profile_id,
                            "prompt_template_version": cand.prompt_template_version,
                        }
                        if cand.candidate_type == "commitment":
                            s.upsert_commitment_candidate(
                                stable_key=stable_key,
                                commitment_actor_class=cand.assignee,
                                **common,
                            )
                        else:
                            s.upsert_task_candidate(
                                stable_key=stable_key,
                                assignee_class=cand.assignee,
                                **common,
                            )
                        # Source refs link to the SAME persisted candidate_id. The source_family is
                        # the authoritative family for THAT ref (packet source_refs / excerpt), never
                        # inferred from the ref string. (Acceptance already rejected unknown refs.)
                        for ref in cand.source_refs:
                            matched = None
                            for ex in excerpts:
                                if str(ex.get("source_ref")) == str(ref):
                                    matched = ex
                                    break
                            body = (matched.get("body_text") or matched.get("subject")) if matched else None
                            evidence = _truncate(body, 400) if body else None
                            s.upsert_candidate_source_ref(
                                source_ref_id=hashlib.sha256(
                                    f"{candidate_id}|{ref}".encode()
                                ).hexdigest()[:24],
                                candidate_type=cand.candidate_type,
                                candidate_id=candidate_id,
                                source_family=known_family.get(str(ref), "unknown"),
                                source_ref_hash=ref,
                                evidence_redacted=evidence,
                            )
                        persisted += 1
                    except Exception:
                        # best effort; do not fail the whole run on one persist
                        continue

            reason = _diagnostic_reason(
                client=client, mock_output=mock_output, error_class=error_class,
                is_timeout=is_timeout, produced=len(parsed), accepted=len(candidates),
                last_parse_error=None, envelope_invalid=envelope_invalid, parsed_ok=True,
            )
            final_report = {
                "produced": len(parsed),
                "accepted": len(candidates),
                "rejected": len(rejections),
                "persisted": persisted,
                "would_persist": len(persistable),
                "dry_run": dry_run,
                "source": source,
                "candidates": [c.model_dump() for c in candidates],
                "rejections": rejections,
                "diagnostics": _build_diagnostics(
                    reason=reason, client=client, mock_output=mock_output, prompt=prompt,
                    excerpts=excerpts, error_class=error_class, parse_meta=parse_meta,
                ),
            }
            break
        except Exception as je:
            last_parse_error = f"json_or_validation_error: {je}"
            # will retry with repair in next outer attempt
            prompt = (
                prompt
                + f"\n\nPREVIOUS OUTPUT FAILED TO PARSE: {last_parse_error}. Return ONLY a JSON object "
                + "with top-level key `candidates` containing an array per the schema."
            )

    # All attempts failed (or no success path taken) — classify the no-output reason.
    if final_report is not None:
        return final_report

    reason = _diagnostic_reason(
        client=client, mock_output=mock_output, error_class=error_class, is_timeout=is_timeout,
        produced=0, accepted=0, last_parse_error=last_parse_error,
        envelope_invalid=envelope_invalid, parsed_ok=parsed_ok,
    )
    return {
        "produced": 0,
        "accepted": 0,
        "rejected": 0,
        "persisted": 0,
        "candidates": [],
        "rejections": [{"reason": last_parse_error or "model_unavailable_or_invalid_output"}],
        "note": "exhausted retries",
        "diagnostics": _build_diagnostics(
            reason=reason, client=client, mock_output=mock_output, prompt=prompt,
            excerpts=excerpts, error_class=error_class, parse_meta=parse_meta,
        ),
    }


def extract_actions_for_packet(
    *,
    packet: dict[str, Any],
    store: Optional[ConstructionStore] = None,
    dry_run: bool = True,
    mock_output: Optional[str] = None,
    client: Optional[OllamaChatClient] = None,
    max_items: int = 20,
) -> dict[str, Any]:
    """Route a bounded packet to extraction by its purpose/allowed-outputs.

    Action/related packets feed the bounded packet content (one thread / one event / a
    deterministically-related small set) to :func:`extract_action_candidates_from_raw`. Packets whose
    purpose does not allow ``candidate_actions`` (triage, summary) NEVER persist task/commitment
    candidates — they return their allowed output shape only. The model never combines unrelated
    records: only relationship-scored ``related_context_action_packet`` content carries >1 source.
    """
    purpose = packet.get("packet_purpose")
    allowed = packet.get("allowed_outputs") or []
    packet_type = packet.get("packet_type")

    # A non-compiled related packet (no relationship passed threshold) must NOT call the model.
    if packet_type == "related_context_action_packet" and packet.get("compiled") is False:
        return {
            "packet_id": packet.get("packet_id"),
            "packet_type": packet_type,
            "packet_purpose": purpose,
            "allowed_outputs": allowed,
            "extracted": False,
            "blocked": True,
            "persisted": 0,
            "candidates": [],
            "note": packet.get("note"),
            "best_confidence": packet.get("best_confidence"),
        }

    if "candidate_actions" not in allowed:
        # Triage / summary purposes are blocked from candidate persistence by contract.
        return {
            "packet_id": packet.get("packet_id"),
            "packet_type": packet_type,
            "packet_purpose": purpose,
            "allowed_outputs": allowed,
            "extracted": False,
            "persisted": 0,
            "candidates": [],
            "note": "purpose_does_not_allow_candidate_actions",
        }

    content = packet.get("content") or {}
    threads = content.get("threads") or []
    events = content.get("events") or []
    email_packet = {"content": {"threads": threads}} if threads else None
    calendar_packet = {"content": {"events": events}} if events else None

    # Authoritative source_family per ref comes from the packet's own source_refs (thread/message/event).
    source_family_map = {
        str(sr["source_ref"]): str(sr["source_family"])
        for sr in (packet.get("source_refs") or [])
        if sr.get("source_ref") and sr.get("source_family")
    }

    report = extract_action_candidates_from_raw(
        raw_email_packet=email_packet,
        raw_calendar_packet=calendar_packet,
        project_key=packet.get("project_key"),
        store=store,
        mock_output=mock_output,
        client=client,
        dry_run=dry_run,
        source="both",
        max_items=max_items,
        source_family_map=source_family_map,
    )
    report["extracted"] = True
    report["packet_id"] = packet.get("packet_id")
    report["packet_type"] = packet_type
    report["packet_purpose"] = purpose
    return report
