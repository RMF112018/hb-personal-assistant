"""Phase 20 schedule-note graph discovery and deterministic candidates.

Schedule-specific only: does not use source-card gc-graph-links, apply, or indexing.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from hb_assistant.obsidian_mcp.schedule_review_note_generator import (
    MANAGED_BEGIN as NOTE_MANAGED_BEGIN,
    MANAGED_END as NOTE_MANAGED_END,
)

SCHEDULE_REVIEW_PREFIX = "Work/HB Personal Assistant/Schedule Review/"
SOURCE_CARD_PREFIX = "Source Notes/Work/"

GRAPH_MANAGED_BEGIN = "<!-- hb-schedule-graph:begin managed -->"
GRAPH_MANAGED_END = "<!-- hb-schedule-graph:end managed -->"

_TRUST_TAGS = {
    "ready": "#schedule-trust-ready",
    "degraded": "#schedule-trust-degraded",
    "blocked": "#schedule-trust-blocked",
}

_FORBIDDEN_PATH = re.compile(
    r"(/Users/|/Volumes/|/home/|[A-Za-z]:\\|\.\./)",
    re.IGNORECASE,
)

_RELATIONSHIP_TYPES = frozenset(
    {
        "same_project_schedule_note",
        "prior_schedule_update",
        "baseline_comparison_related",
        "controls_to_review_summary",
        "portfolio_to_project_schedule",
        "project_note_to_schedule_note",
        "schedule_note_to_safe_source_card",
        "trust_status_related",
        "quality_status_related",
        "review_status_related",
    }
)


@dataclass(frozen=True)
class ScheduleGraphNoteFact:
    note_rel_path: str
    note_title: str
    note_type: str
    project_key: str | None
    project_label: str | None
    schedule_data_date: str | None
    comparison_basis: str | None
    trust_statuses: dict[str, str]
    review_status: dict[str, Any]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class ScheduleGraphCandidate:
    candidate_key: str
    source_note: str
    target_note: str
    relationship_type: str
    confidence: float
    basis: tuple[str, ...]
    recommended: bool
    requires_human_review: bool
    pm_safe_label: str


@dataclass
class SourceCardRef:
    note_rel_path: str
    display_label: str
    project_key: str | None
    document_type: str | None


def _reject_traversal(relative_path: str) -> None:
    if ".." in Path(relative_path).parts:
        raise ValueError("path_traversal_rejected")


def _bounded_rel(vault_root: Path, path: Path) -> str:
    rel = path.resolve().relative_to(vault_root.resolve()).as_posix()
    _reject_traversal(rel)
    return rel


def parse_simple_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    out: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def _note_title_from_text(text: str, rel_path: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return Path(rel_path).stem


def _parse_schedule_date(value: str | None) -> date | None:
    if not value or value in {"—", "-", ""}:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _trust_tags_from_frontmatter(fm: dict[str, str]) -> tuple[str, ...]:
    tags: list[str] = ["#schedule-review", "#schedule-comparison"]
    note_type = fm.get("note_type") or ""
    if note_type == "controls_snapshot":
        tags.append("#schedule-controls")
    if note_type == "portfolio_snapshot":
        tags.append("#schedule-portfolio")
    for key, tag in _TRUST_TAGS.items():
        for status_key in ("analytics_trust_status", "identity_trust_status", "cpm_trust_status"):
            if fm.get(status_key) == key:
                tags.append(tag)
                break
    if fm.get("quality_trust_status") in {"degraded", "blocked"}:
        tags.append("#schedule-quality-review")
    return tuple(sorted(set(tags)))


def discover_schedule_notes(
    vault_root: Path,
    *,
    project_key: str | None = None,
    note_types: Iterable[str] | None = None,
    portfolio_only: bool = False,
) -> list[ScheduleGraphNoteFact]:
    root = vault_root.resolve()
    allowed_types = set(note_types or [])
    facts: list[ScheduleGraphNoteFact] = []
    patterns: list[Path] = []
    if portfolio_only:
        patterns.append(root / "Work/HB Personal Assistant/Schedule Review/Portfolio")
    else:
        patterns.append(root / "Work/HB Personal Assistant/Schedule Review/Projects")
        if not project_key:
            patterns.append(root / "Work/HB Personal Assistant/Schedule Review/Portfolio")

    for base in patterns:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            rel = _bounded_rel(root, path)
            if not rel.startswith(SCHEDULE_REVIEW_PREFIX):
                continue
            text = path.read_text(encoding="utf-8")
            fm = parse_simple_frontmatter(text)
            if fm.get("type") != "schedule_comparison":
                continue
            nt = fm.get("note_type") or ""
            if allowed_types and nt not in allowed_types:
                continue
            pk = fm.get("project_key") or None
            if project_key and pk and pk != project_key and nt != "portfolio_snapshot":
                continue
            if project_key and not pk and nt != "portfolio_snapshot":
                continue
            facts.append(
                ScheduleGraphNoteFact(
                    note_rel_path=rel,
                    note_title=_note_title_from_text(text, rel),
                    note_type=nt,
                    project_key=pk,
                    project_label=fm.get("project_label") or pk,
                    schedule_data_date=fm.get("schedule_data_date") or None,
                    comparison_basis=fm.get("comparison_basis") or None,
                    trust_statuses={
                        "analytics": fm.get("analytics_trust_status") or "unavailable",
                        "identity": fm.get("identity_trust_status") or "unavailable",
                        "cpm": fm.get("cpm_trust_status") or "unavailable",
                        "quality": fm.get("quality_trust_status") or "unavailable",
                    },
                    review_status={},
                    tags=_trust_tags_from_frontmatter(fm),
                )
            )
    return facts


def discover_safe_source_cards(
    vault_root: Path,
    *,
    project_key: str | None = None,
) -> list[SourceCardRef]:
    """Read-only vault scan for generated schedule source cards (no index DB writes)."""
    root = vault_root.resolve()
    cards_dir = root / SOURCE_CARD_PREFIX.rstrip("/")
    if not cards_dir.is_dir():
        return []
    refs: list[SourceCardRef] = []
    for path in sorted(cards_dir.glob("*.md")):
        rel = _bounded_rel(root, path)
        text = path.read_text(encoding="utf-8")
        fm = parse_simple_frontmatter(text)
        if fm.get("note_type") != "source_card":
            continue
        if fm.get("generation_status") not in {None, "", "generated"} and "generated" not in text[:400]:
            continue
        pk = fm.get("project_key") or None
        if project_key and pk != project_key:
            continue
        doc_type = (fm.get("document_type") or "").lower()
        if doc_type and doc_type != "schedule":
            continue
        display = fm.get("title") or Path(path).stem
        if _FORBIDDEN_PATH.search(display) or _FORBIDDEN_PATH.search(rel):
            continue
        refs.append(
            SourceCardRef(
                note_rel_path=rel,
                display_label=str(display)[:120],
                project_key=pk,
                document_type=doc_type or None,
            )
        )
    return refs


def _candidate_key(source: str, target: str, rel_type: str) -> str:
    raw = f"{rel_type}|{source}|{target}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_schedule_wiki_link(target_rel: str, display: str) -> str:
    _reject_traversal(target_rel)
    path = target_rel[:-3] if target_rel.endswith(".md") else target_rel
    safe_display = display.replace("]]", "").strip() or Path(target_rel).stem
    return f"[[{path}|{safe_display}]]"


def build_schedule_graph_candidates(
    facts: list[ScheduleGraphNoteFact],
    *,
    source_cards: list[SourceCardRef] | None = None,
) -> list[ScheduleGraphCandidate]:
    by_project: dict[str, list[ScheduleGraphNoteFact]] = {}
    portfolio: list[ScheduleGraphNoteFact] = []
    for fact in facts:
        if fact.note_type == "portfolio_snapshot":
            portfolio.append(fact)
            continue
        if fact.project_key:
            by_project.setdefault(fact.project_key, []).append(fact)

    candidates: list[ScheduleGraphCandidate] = []
    seen: set[str] = set()

    def add(
        source: ScheduleGraphNoteFact,
        target: ScheduleGraphNoteFact | SourceCardRef,
        rel_type: str,
        confidence: float,
        basis: tuple[str, ...],
        *,
        recommended: bool,
        label: str,
        target_rel: str | None = None,
    ) -> None:
        if rel_type not in _RELATIONSHIP_TYPES:
            return
        target_path = target_rel or (
            target.note_rel_path if isinstance(target, (ScheduleGraphNoteFact, SourceCardRef)) else ""
        )
        key = _candidate_key(source.note_rel_path, target_path, rel_type)
        if key in seen:
            return
        seen.add(key)
        candidates.append(
            ScheduleGraphCandidate(
                candidate_key=key,
                source_note=source.note_rel_path,
                target_note=target_path,
                relationship_type=rel_type,
                confidence=confidence,
                basis=basis,
                recommended=recommended,
                requires_human_review=True,
                pm_safe_label=label,
            )
        )

    for pk, group in sorted(by_project.items()):
        ordered = sorted(
            group,
            key=lambda f: (_parse_schedule_date(f.schedule_data_date) or date.min, f.note_rel_path),
        )
        for i, fact in enumerate(ordered):
            for other in ordered[i + 1 :]:
                if fact.note_rel_path == other.note_rel_path:
                    continue
                add(
                    fact,
                    other,
                    "same_project_schedule_note",
                    0.9,
                    ("same_project_key", "distinct_schedule_note"),
                    recommended=True,
                    label=f"Related schedule note for {pk}",
                )
                if (
                    _parse_schedule_date(fact.schedule_data_date)
                    and _parse_schedule_date(other.schedule_data_date)
                    and _parse_schedule_date(fact.schedule_data_date)
                    < _parse_schedule_date(other.schedule_data_date)
                ):
                    add(
                        other,
                        fact,
                        "prior_schedule_update",
                        0.88,
                        ("same_project_key", "earlier_schedule_date"),
                        recommended=True,
                        label="Prior schedule update for same project",
                    )
            types = {f.note_type for f in ordered}
            if "baseline_comparison" in types and "schedule_update" in types:
                for a in ordered:
                    for b in ordered:
                        if a.note_type == "baseline_comparison" and b.note_type == "schedule_update":
                            add(
                                a,
                                b,
                                "baseline_comparison_related",
                                0.87,
                                ("same_project_key", "baseline_and_update"),
                                recommended=True,
                                label="Baseline comparison related to schedule update",
                            )
            if "controls_snapshot" in types and "review_summary" in types:
                for a in ordered:
                    for b in ordered:
                        if a.note_type == "controls_snapshot" and b.note_type == "review_summary":
                            add(
                                a,
                                b,
                                "controls_to_review_summary",
                                0.86,
                                ("same_project_key", "controls_and_review"),
                                recommended=True,
                                label="Controls snapshot related to review summary",
                            )
            degraded = [
                f
                for f in ordered
                if f.trust_statuses.get("analytics") in {"degraded", "blocked"}
                or f.trust_statuses.get("quality") in {"degraded", "blocked"}
            ]
            if len(degraded) >= 2:
                for a in degraded:
                    for b in degraded:
                        if a.note_rel_path != b.note_rel_path:
                            add(
                                a,
                                b,
                                "trust_status_related",
                                0.75,
                                ("same_project_key", "shared_trust_posture"),
                                recommended=False,
                                label="Shared trust posture across schedule notes",
                            )

        for card in source_cards or []:
            if card.project_key != pk:
                continue
            if not card.display_label:
                continue
            for fact in ordered:
                add(
                    fact,
                    card,
                    "schedule_note_to_safe_source_card",
                    0.7,
                    ("same_project_key", "indexed_source_card"),
                    recommended=False,
                    label=f"Indexed schedule source card for {pk}",
                    target_rel=card.note_rel_path,
                )

    for port in portfolio:
        for pk, group in by_project.items():
            for fact in group:
                if fact.schedule_data_date and port.schedule_data_date:
                    if fact.schedule_data_date[:10] == port.schedule_data_date[:10]:
                        add(
                            port,
                            fact,
                            "portfolio_to_project_schedule",
                            0.85,
                            ("same_schedule_date", "portfolio_roll-up"),
                            recommended=True,
                            label=f"Portfolio snapshot for project {pk}",
                        )

    return sorted(
        candidates,
        key=lambda c: (-c.confidence, c.relationship_type, c.source_note, c.target_note),
    )


def graph_block_entries(text: str) -> list[str] | None:
    if GRAPH_MANAGED_BEGIN not in text or GRAPH_MANAGED_END not in text:
        return None
    start = text.index(GRAPH_MANAGED_BEGIN) + len(GRAPH_MANAGED_BEGIN)
    end = text.index(GRAPH_MANAGED_END)
    return [ln.strip() for ln in text[start:end].splitlines() if ln.strip()]


def render_graph_link_lines(
    candidates: list[ScheduleGraphCandidate],
    facts_by_path: dict[str, ScheduleGraphNoteFact],
    *,
    source_cards: dict[str, SourceCardRef] | None = None,
    recommended_only: bool = True,
) -> dict[str, list[str]]:
    """Map source note path -> deterministic link lines for apply."""
    lines_by_source: dict[str, list[str]] = {}
    cards = source_cards or {}
    for cand in candidates:
        if recommended_only and not cand.recommended:
            continue
        if cand.relationship_type == "schedule_note_to_safe_source_card":
            card = cards.get(cand.target_note)
            display = card.display_label if card else Path(cand.target_note).stem
        else:
            target = facts_by_path.get(cand.target_note)
            display = target.note_title if target else Path(cand.target_note).stem
        link = build_schedule_wiki_link(cand.target_note, display)
        line = (
            f"- {link} — {cand.relationship_type} · deterministic · "
            f"confidence {cand.confidence:.2f}"
        )
        lines_by_source.setdefault(cand.source_note, []).append(line)
    for source, lines in lines_by_source.items():
        lines_by_source[source] = sorted(set(lines))
    return lines_by_source


def tag_recommendations(facts: list[ScheduleGraphNoteFact]) -> dict[str, list[str]]:
    """Report-only tag recommendations; not written to frontmatter."""
    out: dict[str, list[str]] = {}
    for fact in facts:
        out[fact.note_rel_path] = list(fact.tags)
    return out


def assert_report_paths_safe(payload: dict[str, Any]) -> None:
    """Reject absolute paths and traversal in report payloads."""
    blob = str(payload)
    if _FORBIDDEN_PATH.search(blob):
        raise ValueError("report_path_leak_detected")
