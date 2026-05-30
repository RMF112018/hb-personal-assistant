"""Phase 06A — deterministic + heuristic project matching for indexed files.

Assigns each indexed ``construction_drive_items`` file to a construction project
with a qualitative confidence (high|medium|low|none), a status (matched|
low_confidence|unmatched), and reason codes (the signals that fired). Low-confidence
and unmatched files are routed to review (the canonical ``review_required`` /
``review_reason`` drive-item fields).

Pure SQLite + source-registry — **no Microsoft Graph calls, no token, no writeback**.
Signals (per ``project_file_match_signals.json``): source-registry project binding
(deterministic), exact HB project number (``NN-NNN-NN``) in path/name, normalized
project name in path/name, and a literal Procore project id. False-positive
prevention: exact number equality only, ambiguous multi-project signals → low
confidence (never auto-picked), no signal → unmatched (never forced to a target).
"""

from __future__ import annotations

import json
import re
from typing import Optional

from pydantic import BaseModel, Field

from hb_assistant.construction.config import load_source_registry
from hb_assistant.construction.email.project_matcher import HB_PROJECT_NUMBER_RE
from hb_assistant.construction.store import ConstructionStore


def _normalize(text: str) -> str:
    """Lowercase; treat ``_``/``-`` as spaces; collapse whitespace."""
    return re.sub(r"\s+", " ", text.replace("_", " ").replace("-", " ").lower()).strip()


class ProjectDescriptor(BaseModel):
    project_key: str
    project_number: Optional[str] = None  # exact NN-NNN-NN
    name_norm: Optional[str] = None
    procore_project_id: Optional[str] = None

    model_config = {"extra": "forbid"}


class FileMatchResult(BaseModel):
    source_id: str
    drive_item_id: str
    name: Optional[str] = None
    project_key: Optional[str] = None
    project_number_detected: Optional[str] = None
    match_confidence: str  # high | medium | low | none
    match_status: str  # matched | low_confidence | unmatched
    review_required: bool = False
    review_reason: Optional[str] = None
    reason_codes: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class MatchReport(BaseModel):
    command: str = "graph files project-match"
    mode: str  # dry_run | apply
    target_project: Optional[str] = None
    summary: dict[str, int] = Field(default_factory=dict)
    items: list[FileMatchResult] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class FileProjectMatcher:
    """Per-file project matcher over indexed drive items (no Graph, no token)."""

    def __init__(self, store: ConstructionStore) -> None:
        self._store = store

    def _build(self) -> tuple[dict[str, ProjectDescriptor], dict[str, str], list[str]]:
        registry = load_source_registry()
        descriptors: dict[str, ProjectDescriptor] = {}
        for p in registry.projects:
            name = p.project_name_normalized or p.display_name
            descriptors[p.project_key] = ProjectDescriptor(
                project_key=p.project_key,
                project_number=p.project_number,
                name_norm=_normalize(name) if name else None,
                procore_project_id=p.procore_project_id,
            )
        source_to_project: dict[str, str] = {
            s.source_key: s.project_key for s in registry.sources if s.project_key
        }
        source_keys = [s.source_key for s in registry.sources]
        return descriptors, source_to_project, source_keys

    def _match_item(
        self,
        item: dict,
        descriptors: dict[str, ProjectDescriptor],
        source_to_project: dict[str, str],
    ) -> FileMatchResult:
        source_id = item["source_id"]
        name = item.get("name") or ""
        path_text = " ".join(
            v for v in (item.get("path"), item.get("parent_reference_path"), name) if v
        )
        norm_text = _normalize(path_text)

        project_key: Optional[str] = None
        confidence = "none"
        reason_codes: list[str] = []
        project_number_detected: Optional[str] = None

        bound = source_to_project.get(source_id)
        if bound:
            # Deterministic, highest-confidence signal: the source is registry-bound.
            project_key = bound
            confidence = "high"
            reason_codes.append("source_registry_project_key")
            desc = descriptors.get(bound)
            if desc and desc.project_number:
                project_number_detected = desc.project_number
                if desc.project_number in HB_PROJECT_NUMBER_RE.findall(path_text):
                    reason_codes.append("source_registry_project_number")
        else:
            numbers = set(HB_PROJECT_NUMBER_RE.findall(path_text))  # exact NN-NNN-NN tokens
            num_hits = {
                d.project_key
                for d in descriptors.values()
                if d.project_number and d.project_number in numbers
            }
            name_hits = {
                d.project_key
                for d in descriptors.values()
                if d.name_norm and d.name_norm in norm_text
            }
            procore_hits = {
                d.project_key
                for d in descriptors.values()
                if d.procore_project_id and d.procore_project_id in path_text
            }
            if len(num_hits) == 1:
                project_key = next(iter(num_hits))
                confidence = "high"
                num = descriptors[project_key].project_number
                project_number_detected = num
                reason_codes.append(
                    "file_name_project_number"
                    if num and num in HB_PROJECT_NUMBER_RE.findall(name)
                    else "path_project_number"
                )
            elif len(num_hits) > 1:
                confidence = "low"
                reason_codes.append("ambiguous_multiple_project_numbers")
            elif len(name_hits) == 1:
                project_key = next(iter(name_hits))
                confidence = "medium"
                reason_codes.append(
                    "normalized_project_name_file"
                    if descriptors[project_key].name_norm in _normalize(name)
                    else "normalized_project_name_path"
                )
            elif len(name_hits) > 1:
                confidence = "low"
                reason_codes.append("ambiguous_multiple_project_names")
            elif len(procore_hits) == 1:
                project_key = next(iter(procore_hits))
                confidence = "medium"
                reason_codes.append("procore_project_id")
            else:
                confidence = "none"

        status = (
            "matched"
            if confidence in ("high", "medium")
            else "low_confidence"
            if confidence == "low"
            else "unmatched"
        )
        review_required = status in ("low_confidence", "unmatched")
        review_reason = (
            "low_confidence_project_match"
            if status == "low_confidence"
            else "unmatched_no_project"
            if status == "unmatched"
            else None
        )
        return FileMatchResult(
            source_id=source_id,
            drive_item_id=item["drive_item_id"],
            name=item.get("name"),
            project_key=project_key,
            project_number_detected=project_number_detected,
            match_confidence=confidence,
            match_status=status,
            review_required=review_required,
            review_reason=review_reason,
            reason_codes=reason_codes,
        )

    def match(
        self,
        *,
        target_project: Optional[str] = None,
        source_id: Optional[str] = None,
        dry_run: bool = True,
    ) -> MatchReport:
        descriptors, source_to_project, source_keys = self._build()
        sources = [source_id] if source_id else source_keys

        results: list[FileMatchResult] = []
        for sk in sources:
            for item in self._store.list_drive_items(source_id=sk, limit=100000):
                if item.get("deleted") or not item.get("is_file"):
                    continue
                r = self._match_item(item, descriptors, source_to_project)
                results.append(r)
                if not dry_run:
                    self._store.update_drive_item_project_match(
                        source_id=r.source_id,
                        drive_item_id=r.drive_item_id,
                        project_key=r.project_key,
                        project_number_detected=r.project_number_detected,
                        match_confidence=r.match_confidence,
                        match_status=r.match_status,
                        review_required=r.review_required,
                        review_reason=r.review_reason,
                        match_signals_json=json.dumps(r.reason_codes),
                    )

        summary = {
            "total_evaluated": len(results),
            "matched_high": sum(1 for r in results if r.match_confidence == "high"),
            "matched_medium": sum(1 for r in results if r.match_confidence == "medium"),
            "low_confidence": sum(1 for r in results if r.match_status == "low_confidence"),
            "unmatched": sum(1 for r in results if r.match_status == "unmatched"),
            "review_routed": sum(1 for r in results if r.review_required),
        }
        # Report rows: matched-to-target + anything routed to review (when a target is given).
        if target_project:
            shown = [r for r in results if r.project_key == target_project or r.review_required]
        else:
            shown = results
        return MatchReport(
            mode="dry_run" if dry_run else "apply",
            target_project=target_project,
            summary=summary,
            items=shown,
        )
