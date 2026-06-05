"""Phase 08A daily-brief approved local/Obsidian output (Prompt 12).

Renders a deterministic, redacted, marker-bounded daily-brief markdown document from the
brief's cards (never from a model response) and writes it — only on explicit apply — into
the approved Obsidian root at
``<vault>/Construction Intelligence/Phase 08A Daily Briefs/<date>_daily_brief.md``.
Dry-run is the default: it returns the would-be content + a content hash and writes nothing.
The write is marker-bounded (user text outside the markers is preserved) and atomic
(temp file + ``os.replace``). No raw bodies/document text/URLs/secrets are ever written.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from hb_assistant.config.path_policy import PathPolicy

if TYPE_CHECKING:
    from .models import DailyBriefContext


class BriefWriteResult(NamedTuple):
    """Outcome of an approved-output write (dry-run computes the hash, writes nothing)."""

    written: bool
    output_path_redacted: str | None
    output_path_hash: str | None
    content_hash: str

SECTION_START = "<!-- HB-SECOND-BRAIN-DAILY-BRIEF:START -->"
SECTION_END = "<!-- HB-SECOND-BRAIN-DAILY-BRIEF:END -->"
_VAULT_SUBDIR = Path("Construction Intelligence") / "Phase 08A Daily Briefs"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ensure_markers(existing: str, start: str, end: str) -> str:
    if start in existing and end in existing:
        return existing
    if existing and not existing.endswith("\n"):
        existing += "\n"
    return existing + f"\n{start}\n{end}\n"


def _replace_bounded(existing: str, inner: str, start: str, end: str) -> str:
    pattern = re.compile(rf"({re.escape(start)})(.*?)({re.escape(end)})", re.DOTALL)
    return pattern.sub(rf"\1\n{inner}\n\3", existing)


def _atomic_write_text(target: Path, content: str) -> None:
    """Atomic write (temp + os.replace) within the target directory."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, target)
    except Exception:
        with contextlib.suppress(Exception):
            tmp_path.unlink(missing_ok=True)
        raise


def resolve_brief_path(brief_date: str, *, vault_brief_dir: str | Path | None = None) -> Path:
    """Resolve the approved output path for a brief date (vault-governed by default)."""
    base = Path(vault_brief_dir) if vault_brief_dir is not None else (
        PathPolicy().get_vault_root() / _VAULT_SUBDIR
    )
    return base / f"{brief_date}_daily_brief.md"


def _line(title: str, source_refs: list[dict[str, str]], tier: int) -> str:
    refs = " ".join(f"{r.get('source_family', '')}:{r.get('source_ref', '')}" for r in source_refs)
    suffix = f" (source: {refs})" if refs else ""
    return f"- [tier {tier}] {title}{suffix}"


def render_brief_markdown(context: DailyBriefContext) -> str:
    """Render the redacted, deterministic inner brief content (no raw, no model text)."""
    lines: list[str] = [
        f"# Daily Brief — {context.brief_date}",
        "",
        (
            f"_Advisory only. status={context.status}; "
            f"degradation={context.degradation_mode}; "
            f"review_tier={context.review_tier} ({context.review_tier_reason_code}); "
            f"source_coverage={context.source_coverage}. "
            "Tier-3 items are routed to mandatory review and never presented as fact._"
        ),
        "",
        "## Priority Actions",
        *(
            [_line(c.title_redacted, c.source_refs, c.review_tier) for c in context.attention_cards]
            or ["_No priority actions._"]
        ),
        "",
        "## Waiting On / Warnings",
        *(
            [_line(c.summary_redacted, c.source_refs, c.review_tier) for c in context.warning_cards]
            or ["_No stale/conflict warnings._"]
        ),
        "",
        "## Meeting Prep",
        *(
            [_line(c.title_redacted, c.source_refs, c.review_tier) for c in context.meeting_cards]
            or ["_No meeting prep source model available._"]
        ),
        "",
        "## Review exceptions (capped; see `second-brain review burden` for full clusters)",
        *(
            [
                _line(c.title_redacted, c.source_refs, c.review_tier)
                for c in (context.review_required_cards or [])[:10]
            ]
            or ["- No Tier-C exceptions in current brief context."]
        ),
        "",
        "Batched/suppressed (advisory only; not promoted; high-impact summarized not itemized):",
        f"- review load from triage: total={getattr(context.review_load, 'total_review_items', 0)} tier3={getattr(context.review_load, 'tier_3_count', 0)}",
        "- Low-risk metadata-only source-linked signals (after two-step impact classification) are retained as advisory with labels; financial ledger tracked separately and does not block low-risk non-financial advisory.",
        "- Weak candidates suppressed from standard answers per policy budget and batch rules. High-impact categories always visible in summary + top clusters only within operator daily budget.",
        "- Recommended: run `hb-assistant second-brain review burden --json` and `second-brain review queue --top 10 --json` for operator action (capped).",
        "",
        "## Project Signals",
        *(
            [
                _line(
                    f"project {c.project_key}: {c.item_count} item(s), "
                    f"{c.review_required_count} review-required",
                    c.source_refs,
                    c.max_review_tier,
                )
                for c in context.project_cards
            ]
            or ["_No project signals._"]
        ),
    ]
    if context.warnings:
        lines += ["", "## Coverage Notes", *(f"- {w}" for w in context.warnings)]
    return "\n".join(lines)


def write_brief_output(
    *,
    brief_date: str,
    content: str,
    vault_brief_dir: str | Path | None = None,
    apply: bool = False,
) -> BriefWriteResult:
    """Frame the content in markers and (only on apply) atomically write it to the vault.

    Dry-run computes the would-be framed content + hash but writes nothing.
    """
    target = resolve_brief_path(brief_date, vault_brief_dir=vault_brief_dir)
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    framed = _ensure_markers(existing, SECTION_START, SECTION_END)
    new_content = _replace_bounded(framed, content.strip(), SECTION_START, SECTION_END)
    content_hash = _sha256(new_content)

    if not apply:
        return BriefWriteResult(
            written=False,
            output_path_redacted=None,
            output_path_hash=None,
            content_hash=content_hash,
        )

    _atomic_write_text(target, new_content)
    try:
        redacted = str(target.relative_to(PathPolicy().get_vault_root()))
    except ValueError:
        redacted = f"{target.parent.name}/{target.name}"
    return BriefWriteResult(
        written=True,
        output_path_redacted=redacted,
        output_path_hash=content_hash,
        content_hash=content_hash,
    )
