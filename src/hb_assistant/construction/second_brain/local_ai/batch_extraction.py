"""Phase 10A batch action extraction (local, dry-run-first, capped apply).

Operationalizes the validated single-packet ``extract-packet`` path over many email threads:
selects bounded ``email_thread_action_packet`` units, runs the SAME extraction path per thread,
aggregates safe summary counters, and writes a redacted local review artifact. Apply is explicit,
capped by ``max_persist`` (actual persisted candidates, not packets), and skips stable keys already
present. No broad raw packets, no combining of unrelated records, no raw-content or writeback exposure.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from hb_assistant.construction.second_brain.local_ai.packet_builders import (
    build_email_thread_action_packet,
)
from hb_assistant.construction.second_brain.local_ai.raw_action_intelligence import (
    extract_actions_for_packet,
)
from hb_assistant.construction.store import ConstructionStore

try:  # OllamaChatClient is only used for typing; never required for mock/dry-run paths.
    from hb_assistant.construction.classification.client import OllamaChatClient
except Exception:  # pragma: no cover - defensive
    OllamaChatClient = Any  # type: ignore[assignment,misc]

SUPPORTED_SOURCES = ("email",)
_ARTIFACT_PREFIX = "phase10a_extract_packets_"

# Defensive cap on serialized thread size. The packet builder already hard-caps the
# MODEL-facing output (≤6 messages × ≤1200 chars, ≤12KB), so the model never sees a
# giant thread; this guard avoids paying pathological parse/sort cost on a single
# multi-MB ``messages_json`` blob (real data has threads up to ~4.5MB). Oversized
# threads are skipped and counted, never silently truncated.
MAX_THREAD_MESSAGES_JSON_CHARS = 1_500_000


class UnsupportedBatchSourceError(ValueError):
    """Raised (fail-closed) when an unimplemented --source is requested."""


def _candidate_type_bucket(candidate_type: Optional[str]) -> str:
    if candidate_type in ("task", "commitment", "question"):
        return candidate_type
    if candidate_type == "risk_signal":
        return "risk"
    return "other"


def existing_stable_keys(store: ConstructionStore) -> set[str]:
    """All persisted task + commitment stable keys (for cross-batch duplicate skipping)."""
    keys: set[str] = set()
    for row in store.list_task_candidates(limit=100000):
        sk = row.get("stable_key")
        if sk:
            keys.add(str(sk))
    for row in store.list_commitment_candidates(limit=100000):
        sk = row.get("stable_key")
        if sk:
            keys.add(str(sk))
    return keys


def _processed_thread_refs(store: ConstructionStore) -> set[str]:
    """thread refs already represented in persisted candidate source refs (for --only-unprocessed)."""
    refs: set[str] = set()
    for row in store.list_candidate_source_refs(limit=100000):
        h = row.get("source_ref_hash")
        if h:
            refs.add(str(h))
    return refs


def _select_email_threads(
    *,
    store: ConstructionStore,
    limit: int,
    offset: int,
    thread_refs: Optional[list[str]],
    only_unprocessed: bool,
    max_messages_json_chars: Optional[int] = MAX_THREAD_MESSAGES_JSON_CHARS,
) -> tuple[list[dict[str, Any]], int, int]:
    """Select email-thread records, longest serialized thread first (matches the validated manual loop).

    Returns (selected, skipped_unprocessed_count, skipped_oversized_count).
    """
    rows = store.list_email_thread_raw_context(limit=100000)
    # Prefer rows that actually carry messages (messages_json IS NOT NULL / non-empty).
    rows = [r for r in rows if (r.get("messages_json") or "").strip() not in ("", "[]", "null")]
    if thread_refs:
        wanted = {str(t) for t in thread_refs}
        rows = [r for r in rows if str(r.get("thread_ref")) in wanted]
    # Defensive: drop pathologically large serialized threads (counted, never truncated).
    skipped_oversized = 0
    if max_messages_json_chars is not None:
        kept_size = [r for r in rows if len(r.get("messages_json") or "") <= max_messages_json_chars]
        skipped_oversized = len(rows) - len(kept_size)
        rows = kept_size
    skipped_unprocessed = 0
    if only_unprocessed:
        seen = _processed_thread_refs(store)
        kept = [r for r in rows if str(r.get("thread_ref")) not in seen]
        skipped_unprocessed = len(rows) - len(kept)
        rows = kept
    # ORDER BY length(messages_json) DESC, then thread_ref for a stable tiebreak.
    rows.sort(key=lambda r: (-(len(r.get("messages_json") or "")), str(r.get("thread_ref") or "")))
    selected = rows[offset : offset + limit] if limit is not None else rows[offset:]
    return selected, skipped_unprocessed, skipped_oversized


def _safe_rejections(rejections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Redacted rejection view: reason + unresolved aliases only (never raw model items/candidates)."""
    safe: list[dict[str, Any]] = []
    for rej in rejections or []:
        entry: dict[str, Any] = {"reason": str(rej.get("reason"))}
        if rej.get("unresolved_refs"):
            entry = {**entry, "unresolved_refs": rej.get("unresolved_refs")}
        safe.append(entry)
    return safe


def _artifact_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_batch_extraction(
    *,
    source: str,
    store: ConstructionStore,
    limit: int = 50,
    dry_run: bool = True,
    max_persist: Optional[int] = None,
    client: Optional["OllamaChatClient"] = None,
    model_name: Optional[str] = None,
    mock_output_map: Optional[Mapping[str, str]] = None,
    mock_output: Optional[str] = None,
    offset: int = 0,
    thread_refs: Optional[list[str]] = None,
    only_unprocessed: bool = False,
    max_items: int = 20,
    write_artifact: bool = True,
    artifact_dir: str = "/tmp",
    timestamp: Optional[str] = None,
    max_messages_json_chars: Optional[int] = MAX_THREAD_MESSAGES_JSON_CHARS,
) -> dict[str, Any]:
    """Run Phase 10A extraction over a bounded batch of email-thread packets.

    Dry-run is the default (zero writes). ``--apply`` (dry_run=False) requires ``max_persist`` and caps
    ACTUAL persisted candidates across the whole batch; once the cap is hit, remaining packets are
    processed in dry-run (counted, never written). Each thread becomes one ``email_thread_action_packet``
    and flows through the same extraction path as single ``extract-packet`` — source aliases, object-root
    output, pre-validation review normalization, and traceability defaults are preserved.
    """
    if source not in SUPPORTED_SOURCES:
        raise UnsupportedBatchSourceError(
            f"unsupported source {source!r}; supported: {', '.join(SUPPORTED_SOURCES)}"
        )
    if not dry_run and max_persist is None:
        raise ValueError("apply requires max_persist (cap on actual persisted candidates)")

    selected, skipped_unprocessed, skipped_oversized = _select_email_threads(
        store=store, limit=limit, offset=offset, thread_refs=thread_refs,
        only_unprocessed=only_unprocessed, max_messages_json_chars=max_messages_json_chars,
    )

    # Existing keys are skipped (counted, not rewritten); newly-persisted keys are added as we go so a
    # duplicate within the same batch is also skipped.
    known_keys = existing_stable_keys(store) if not dry_run else set()

    summary = {
        "produced": 0, "accepted": 0, "rejected": 0, "would_persist": 0, "persisted": 0,
        "skipped_existing": 0, "unsupported_candidate_type": 0, "no_candidates": 0,
        "blocked": 0, "failed": 0,
    }
    candidate_types = {"task": 0, "commitment": 0, "question": 0, "risk": 0, "other": 0}
    safety_categories: dict[str, int] = {}
    recommended_actions: dict[str, int] = {}
    assignee_waiting: dict[str, int] = {}
    rejection_reason_counts: dict[str, int] = {}
    source_alias_failures: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    remaining: Optional[int] = max_persist if (not dry_run and max_persist is not None) else None

    for rec in selected:
        thread_ref = str(rec.get("thread_ref"))
        mock = (mock_output_map or {}).get(thread_ref, mock_output)
        try:
            packet = build_email_thread_action_packet(thread_ref=thread_ref, store=store)
        except Exception as e:
            summary["failed"] += 1
            results.append({
                "thread_ref": thread_ref, "packet_id": None, "packet_type": None,
                "failed": True, "error": str(e)[:200],
            })
            continue

        # Per-packet apply posture: persist only while budget remains; otherwise dry-run + count.
        packet_dry_run = dry_run
        packet_max_persist: Optional[int] = None
        if not dry_run:
            if remaining is not None and remaining <= 0:
                packet_dry_run = True
            else:
                packet_max_persist = remaining

        try:
            report = extract_actions_for_packet(
                packet=packet, store=store, dry_run=packet_dry_run, mock_output=mock,
                client=client, max_items=max_items, max_persist=packet_max_persist,
                existing_stable_keys=known_keys,
            )
        except Exception as e:
            summary["failed"] += 1
            results.append({
                "thread_ref": thread_ref, "packet_id": packet.get("packet_id"),
                "packet_type": packet.get("packet_type"), "failed": True, "error": str(e)[:200],
            })
            continue

        produced = int(report.get("produced", 0) or 0)
        accepted = int(report.get("accepted", 0) or 0)
        rejected = int(report.get("rejected", 0) or 0)
        would_persist = int(report.get("would_persist", 0) or 0)
        persisted = int(report.get("persisted", 0) or 0)
        skipped_existing = int(report.get("skipped_existing", 0) or 0)
        blocked = bool(report.get("blocked"))
        unsupported = max(accepted - would_persist, 0)

        summary["produced"] += produced
        summary["accepted"] += accepted
        summary["rejected"] += rejected
        summary["would_persist"] += would_persist
        summary["persisted"] += persisted
        summary["skipped_existing"] += skipped_existing
        summary["unsupported_candidate_type"] += unsupported
        if blocked:
            summary["blocked"] += 1
        if produced == 0 and not blocked:
            summary["no_candidates"] += 1

        for cand in report.get("candidates", []) or []:
            candidate_types[_candidate_type_bucket(cand.get("candidate_type"))] += 1
            sc = str(cand.get("safety_category"))
            safety_categories[sc] = safety_categories.get(sc, 0) + 1
            ra = str(cand.get("recommended_next_action"))
            recommended_actions[ra] = recommended_actions.get(ra, 0) + 1
            aw = f"{cand.get('assignee')}/{cand.get('waiting_state')}"
            assignee_waiting[aw] = assignee_waiting.get(aw, 0) + 1

        for rej in report.get("rejections", []) or []:
            reason = str(rej.get("reason"))
            rejection_reason_counts[reason] = rejection_reason_counts.get(reason, 0) + 1
            if reason == "source_alias_not_in_packet":
                source_alias_failures.append({
                    "thread_ref": thread_ref,
                    "unresolved_refs": rej.get("unresolved_refs") or [],
                })

        # Apply-budget accounting + cross-batch duplicate dedup.
        if remaining is not None:
            remaining -= persisted
        for sk in report.get("persisted_stable_keys", []) or []:
            known_keys.add(str(sk))

        results.append({
            "thread_ref": thread_ref,
            "packet_id": report.get("packet_id"),
            "packet_type": report.get("packet_type"),
            "produced": produced,
            "accepted": accepted,
            "rejected": rejected,
            "would_persist": would_persist,
            "persisted": persisted,
            "skipped_existing": skipped_existing,
            "unsupported_candidate_type": unsupported,
            "blocked": blocked,
            "diagnostics_reason": (report.get("diagnostics") or {}).get("reason"),
            "diagnostics": report.get("diagnostics"),
            "accepted_candidates": report.get("candidates", []),
            "rejections": _safe_rejections(report.get("rejections", [])),
        })

    top_rejection_reasons = [
        {"reason": r, "count": c}
        for r, c in sorted(rejection_reason_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ][:10]

    payload: dict[str, Any] = {
        "command": "second-brain extract-packets",
        "ok": True,
        "applied": not dry_run,
        "source": source,
        "limit": limit,
        "max_persist": max_persist,
        "model_name": model_name or ("mock" if (mock_output_map or mock_output) is not None else None),
        "processed_packets": len(results),
        "skipped_unprocessed": skipped_unprocessed,
        "skipped_oversized": skipped_oversized,
        "summary": summary,
        "candidate_types": candidate_types,
        "safety_categories": safety_categories,
        "recommended_actions": recommended_actions,
        "assignee_waiting": assignee_waiting,
        "top_rejection_reasons": top_rejection_reasons,
        "source_alias_failures": source_alias_failures,
        "guardrails": {
            "dry_run_default": True,
            "apply_requires_max_persist": True,
            "no_raw_persistence": True,
            "no_writeback": True,
            "one_unit_per_packet": True,
            "no_broad_raw_packets": True,
        },
        "artifact_path": None,
        "results": results,
    }

    if write_artifact:
        ts = timestamp or _artifact_timestamp()
        path = os.path.join(artifact_dir, f"{_ARTIFACT_PREFIX}{ts}.json")
        payload = {**payload, "artifact_path": path}
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, default=str)
        except Exception:
            # Artifact is best-effort; never fail the run because /tmp is unwritable.
            payload = {**payload, "artifact_path": None, "artifact_error": "artifact_write_failed"}

    return payload
