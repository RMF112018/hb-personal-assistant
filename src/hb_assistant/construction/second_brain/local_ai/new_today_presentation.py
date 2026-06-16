"""Phase 10 (252) — New Today presentation (pure, deterministic, raw-safe).

Turns the in-memory :class:`~hb_assistant.construction.second_brain.local_ai.new_today_digest.
DailyBriefChangeEvent` list into the single render model that BOTH the Markdown brief and the browser
HTML consume, so the two surfaces never drift. The model is grouped by attention class in the
required order (Needs your attention → Team follow-up / monitor → Awareness only); empty groups are
omitted (never rendered as ``None``).

Pure: no store, no I/O, no wall-clock. Every user-facing line passes the same output fence the rest
of the brief uses (:func:`daily_brief_presentation.assert_clean_display`) plus the forbidden-token
scan, so a regression that leaks an internal artifact or raw private content fails loudly.
"""

from __future__ import annotations

from typing import Any, Optional

from .daily_brief_presentation import assert_clean_display
from .model_eval_metrics import scan_text_for_forbidden
from .new_today_digest import ATTENTION_LABEL, ATTENTION_ORDER

HEADER = "Today's Daily Brief"
SECTION_TITLE = "New Today"
DIAGNOSTICS_TITLE = "Run details / diagnostics"

#: Deterministic family order within an attention group (most operationally-decisive first).
_FAMILY_ORDER = {"email": 0, "procore": 1, "calendar": 2, "sharepoint": 3}


def subhead(brief_date: str, lookahead_end_date: str) -> str:
    """The required subhead contract (README): top items for the date + prep through the look-ahead."""
    return f"Summary of the top items for {brief_date} and prep through {lookahead_end_date}"


def _item_text(ev: Any) -> Optional[str]:
    """Combine an event's deterministic summary + recommended action into one raw-safe bullet line.

    Returns ``None`` if the composed line carries any forbidden token (raw leak) — the caller drops
    it rather than surface unsafe content.
    """
    summary = str(getattr(ev, "summary_text", "") or "").strip()
    action = str(getattr(ev, "recommended_action", "") or "").strip()
    if not summary:
        return None
    text = summary if (not action or summary.endswith(action)) else f"{summary} {action}"
    if scan_text_for_forbidden(text):
        return None
    return text


def _sort_key(ev: Any) -> tuple[int, str, str]:
    fam = _FAMILY_ORDER.get(str(getattr(ev, "source_family", "")), 9)
    return (fam, str(getattr(ev, "event_timestamp", "") or ""), str(getattr(ev, "event_id", "")))


def build_render_model(digest: dict[str, Any], *, status: str = "ok") -> dict[str, Any]:
    """Build the shared New Today render model (pure dict of strings) from a digest result.

    Groups events by attention class (required order, empty groups omitted); composes a concise
    user-facing degraded warning when the run status is not clean or the email usefulness gate fired
    (technical detail stays in the collapsed diagnostics block, not here).
    """
    brief_date = str(digest.get("brief_date") or "")
    lookahead_end = str(digest.get("lookahead_end_date") or "")
    events = list(digest.get("events") or [])
    gates = dict(digest.get("gates") or {})

    groups: list[dict[str, Any]] = []
    total = 0
    for attention in ATTENTION_ORDER:
        bucket = sorted(
            (e for e in events if str(getattr(e, "attention_class", "")) == attention),
            key=_sort_key,
        )
        items: list[str] = []
        for ev in bucket:
            text = _item_text(ev)
            if text:
                items.append(text)
        if items:
            groups.append(
                {"attention_class": attention, "label": ATTENTION_LABEL[attention], "items": items}
            )
            total += len(items)

    degraded = status not in ("ok", "success") or bool(gates.get("email_degraded"))
    warning: Optional[str] = None
    if degraded:
        warning = (
            "Some sources were degraded for this brief — see Run details / diagnostics below. "
            "The items above are complete for the sources that refreshed cleanly."
        )

    return {
        "header": HEADER,
        "subhead": subhead(brief_date, lookahead_end),
        "section_title": SECTION_TITLE,
        "brief_date": brief_date,
        "lookahead_end_date": lookahead_end,
        "groups": groups,
        "degraded_warning": warning,
        "total_items": total,
        "empty": total == 0,
    }


def render_markdown(model: dict[str, Any]) -> str:
    """Deterministic, sanitized New Today Markdown (header → subhead → grouped business events).

    Passes the shared output fence so any leaked internal artifact or raw content fails loudly.
    """
    lines: list[str] = [f"# {model['header']}", "", f"_{model['subhead']}_", ""]
    if model.get("degraded_warning"):
        lines += [f"> ⚠️ {model['degraded_warning']}", ""]
    lines += [f"## {model['section_title']}", ""]
    if model.get("empty"):
        lines += ["_No notable business changes in the most recent refresh window._", ""]
    else:
        for group in model["groups"]:
            lines.append(f"### {group['label']}")
            lines.extend(f"- {item}" for item in group["items"])
            lines.append("")
    markdown = "\n".join(lines).strip() + "\n"
    assert_clean_display(markdown, where="New Today brief")
    return markdown
