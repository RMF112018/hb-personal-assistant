"""Deterministic action candidate extractor (no LLM, no Graph, local only).

Uses discovered classification signals (bobby_mention, possible_action_or_waiting via heuristics)
and/or store signals. stable_key deterministic + source-linked.
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional

from hb_assistant.actions.models import ActionItem
from hb_assistant.store.repositories import Store


def extract_candidates(
    signals: list[dict[str, Any]] | None = None,
    store: Optional[Store] = None,
    limit: int = 50,
) -> list[ActionItem]:
    """Generate deduped ActionItem candidates.

    - signals: list of classification-like dicts (e.g. {"classifications": ["bobby_mention"], "message_source_record_id": 123, ...})
    - Falls back to recent store action_items for seeding/dedup.
    - action_type: "task" default, "waiting_on" for waiting heuristics.
    - No full content ever.
    """
    cands: list[ActionItem] = []
    seen: set[str] = set()
    sigs = signals or []

    for sig in sigs:
        src_id = sig.get("message_source_record_id") or sig.get("source_id") or sig.get("source_record_id") or 0
        raw_title = sig.get("title") or sig.get("excerpt") or sig.get("match_excerpt_redacted") or "Follow up on item"
        title = str(raw_title)[:200].strip()
        classifications = str(sig.get("classifications", ""))
        a_type = "waiting_on" if ("waiting" in classifications.lower() or "review by" in classifications.lower()) else "task"
        if "bobby_mention" in classifications:
            a_type = "task"

        h = hashlib.sha256(title[:100].encode("utf-8")).hexdigest()[:12]
        sk = f"action:{a_type}:{src_id}:{h}"
        if sk in seen:
            continue
        seen.add(sk)

        conf = 0.85 if "bobby_mention" in classifications else 0.65
        sources = [{"source_id": src_id, "link_type": "parsed_from"}]
        cands.append(
            ActionItem(
                stable_key=sk,
                title=title,
                action_type=a_type,
                confidence=conf,
                sources=sources,
            )
        )
        if len(cands) >= limit:
            break

    # Fallback / dedup seed from existing store items (discovered get_recent_action_items)
    if store is not None and len(cands) < limit:
        try:
            recent = store.get_recent_action_items(limit=limit)
            for r in recent:
                sk = r.get("stable_key")
                if sk and sk not in seen:
                    seen.add(sk)
                    cands.append(
                        ActionItem(
                            stable_key=sk,
                            title=r.get("title", "Existing item"),
                            action_type=r.get("action_type", "task"),
                            due_date=r.get("due_date"),
                            confidence=r.get("confidence", 0.5),
                            status=r.get("status", "open"),
                            sources=[{"source_id": r.get("id"), "link_type": "existing"}],
                        )
                    )
        except Exception:
            pass  # never fail extraction on store read issues for dry-run safety

    return cands[:limit]
