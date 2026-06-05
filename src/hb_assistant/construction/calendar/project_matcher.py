"""Phase 07B Prompt 05 — calendar event → project matching (deterministic + heuristic).

Links indexed calendar events to known construction projects and writes **candidate**
rows to ``calendar_project_match_candidates``. Pure local SQLite + source registry —
no Microsoft Graph calls, no token, no writeback to any external system.

Matching runs entirely over the **redacted** index: an event exposes only
``subject_token_hashes`` (hashes of subject tokens + the hash of any full HB project
number, stored by the Prompt 04 indexer) and ``organizer_domain``. The matcher hashes
each known project's number and name tokens the same way and tests membership/overlap:

- ``project_number`` — the full HB project-number hash is present → ``deterministic``
  (0.95). Exact (full-number) hash equality, so no false-positive on number fragments.
- ``project_name_tokens`` — distinctive project-name token overlap → ``moderate`` (≥2)
  or ``weak`` (1); always review-required.
- ``participant_domain`` — supported but inert until a project-domain registry exists.

No auto-promotion: every candidate is persisted with ``promotion_status='candidate'``
and the event index is never written. When an event matches more than one project, all
of its candidates are flagged ``review_required`` with reason
``conflicting_project_signals`` (even a deterministic one). Private events carry no
subject tokens (Prompt 04 omits them) and therefore produce no candidate.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from pydantic import BaseModel, Field

from hb_assistant.construction.calendar.contracts import load_calendar_project_match_contract
from hb_assistant.construction.config import load_source_registry
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.normalize.redaction import hash_value

# Confidence classes / scores (mirror calendar_project_match_contract.json).
_CONF_DETERMINISTIC = ("deterministic", 0.95)
_CONF_MODERATE = ("moderate", 0.6)
_CONF_WEAK = ("weak", 0.0)
# Classes that route to human review (contract review_required_when).
_REVIEW_CLASSES = {"weak", "moderate", "model_proposed", "sensitive"}
_SAMPLE_MATCHED_TOKENS = 8


def _name_token_hashes(name: Optional[str]) -> set[str]:
    """Hash a project name's tokens the SAME way the Prompt 04 indexer hashes a
    subject (split on \\W+, lowercase, len>=2, sha256-16)."""
    if not name:
        return set()
    tokens = {t.lower() for t in re.split(r"\W+", name) if len(t) >= 2}
    return {h for h in (hash_value(t) for t in tokens) if h}


class ProjectDescriptor(BaseModel):
    """Hashed project identifiers used for redacted-token matching."""

    project_key: str
    project_number: Optional[str] = None
    full_number_hash: Optional[str] = None
    name_token_hashes: set[str] = Field(default_factory=set)

    model_config = {"extra": "forbid"}


class CalendarMatchCandidate(BaseModel):
    """One persisted candidate (safe fields only — no raw subject/number/email)."""

    candidate_id: str
    event_index_id: str
    project_key: str
    candidate_type: str
    confidence: float
    confidence_class: str
    deterministic: bool
    review_required: bool
    promotion_status: str = "candidate"
    signals: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class MatchReport(BaseModel):
    command: str = "graph calendar project-match"
    mode: str  # dry_run | apply
    target_project: Optional[str] = None
    summary: dict[str, int] = Field(default_factory=dict)
    candidates: list[CalendarMatchCandidate] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class CalendarProjectMatcher:
    """Per-event project matcher over the redacted calendar index (no Graph, no token)."""

    def __init__(self, store: ConstructionStore, *, registry: Any = None) -> None:
        self._store = store
        self._registry = registry
        # Validate the contract (asserts auto_promotion_allowed is false).
        load_calendar_project_match_contract()

    def _descriptors(self) -> list[ProjectDescriptor]:
        registry = self._registry or load_source_registry()
        descriptors: list[ProjectDescriptor] = []
        for p in registry.projects:
            number = p.project_number
            name = p.project_name_normalized or p.display_name
            descriptors.append(
                ProjectDescriptor(
                    project_key=p.project_key,
                    project_number=number,
                    full_number_hash=hash_value(number) if number else None,
                    name_token_hashes=_name_token_hashes(name),
                )
            )
        return descriptors

    def _candidates_for_event(
        self, event: dict[str, Any], descriptors: list[ProjectDescriptor]
    ) -> list[CalendarMatchCandidate]:
        token_hashes = set(event.get("subject_token_hashes") or [])
        if event.get("is_private") or not token_hashes:
            return []

        raw: list[CalendarMatchCandidate] = []
        for desc in descriptors:
            number_match = bool(desc.full_number_hash and desc.full_number_hash in token_hashes)
            name_overlap = sorted(desc.name_token_hashes & token_hashes)
            if number_match:
                ctype, (cclass, conf), det = "project_number", _CONF_DETERMINISTIC, True
            elif len(name_overlap) >= 2:
                ctype, (cclass, conf), det = "project_name_tokens", _CONF_MODERATE, False
            elif len(name_overlap) == 1:
                ctype, (cclass, conf), det = "project_name_tokens", _CONF_WEAK, False
            else:
                continue

            signals = {
                "candidate_type": ctype,
                "project_number_hash_match": number_match,
                "name_token_overlap": len(name_overlap),
                "matched_token_hashes": (
                    ([desc.full_number_hash] if number_match else []) + name_overlap
                )[:_SAMPLE_MATCHED_TOKENS],
                "event_token_count": len(token_hashes),
                "is_cancelled": bool(event.get("is_cancelled")),
                "conflicting": False,
            }
            raw.append(
                CalendarMatchCandidate(
                    candidate_id=hash_value(f"{event['event_index_id']}|{desc.project_key}|{ctype}")
                    or f"{event['event_index_id']}:{desc.project_key}",
                    event_index_id=event["event_index_id"],
                    project_key=desc.project_key,
                    candidate_type=ctype,
                    confidence=conf,
                    confidence_class=cclass,
                    deterministic=det,
                    review_required=cclass in _REVIEW_CLASSES,
                    signals=signals,
                )
            )

        # conflicting_project_signals: >1 distinct project matched this event.
        distinct_projects = {c.project_key for c in raw}
        if len(distinct_projects) > 1:
            for c in raw:
                c.review_required = True
                c.signals["conflicting"] = True
        return raw

    def match(
        self,
        *,
        target_project: Optional[str] = None,
        source_id: Optional[str] = None,
        dry_run: bool = True,
    ) -> MatchReport:
        descriptors = self._descriptors()
        events = self._store.list_calendar_event_index(source_id=source_id)

        all_candidates: list[CalendarMatchCandidate] = []
        events_matched = 0
        events_unmatched = 0
        for event in events:
            cands = self._candidates_for_event(event, descriptors)
            if cands:
                events_matched += 1
            elif not event.get("is_private"):
                events_unmatched += 1
            for c in cands:
                all_candidates.append(c)
                if not dry_run:
                    self._store.upsert_calendar_project_match_candidate(
                        candidate_id=c.candidate_id,
                        event_index_id=c.event_index_id,
                        project_key=c.project_key,
                        candidate_type=c.candidate_type,
                        signals_json=json.dumps(c.signals, sort_keys=True),
                        confidence=c.confidence,
                        confidence_class=c.confidence_class,
                        deterministic=c.deterministic,
                        model_proposed=False,
                        review_required=c.review_required,
                        promotion_status="candidate",
                    )

        summary = {
            "events_evaluated": len(events),
            "events_matched": events_matched,
            "events_unmatched": events_unmatched,
            "candidates_created": len(all_candidates),
            "deterministic": sum(
                1 for c in all_candidates if c.confidence_class == "deterministic"
            ),
            "moderate": sum(1 for c in all_candidates if c.confidence_class == "moderate"),
            "weak": sum(1 for c in all_candidates if c.confidence_class == "weak"),
            "review_routed": sum(1 for c in all_candidates if c.review_required),
            "conflicting": sum(1 for c in all_candidates if c.signals.get("conflicting")),
        }
        shown = all_candidates
        if target_project:
            shown = [c for c in all_candidates if c.project_key == target_project]
        return MatchReport(
            mode="dry_run" if dry_run else "apply",
            target_project=target_project,
            summary=summary,
            candidates=shown,
        )
