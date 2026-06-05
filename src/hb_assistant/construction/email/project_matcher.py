"""Phase 06 — deterministic project matching for email metadata (pure logic).

Scores a message's redacted-in-memory metadata (subject, bodyPreview, sender
domain, participant domains, webLink) against a project descriptor and returns
weighted match signals. Pure and side-effect-free: no I/O, no persistence — the
discovery service persists results. Confidence bands follow the package's
`project_match_signals.json` + `05_SCHEMA_AND_DATA_MODEL.md`.

Project descriptors are built from the seed registries (the authoritative source;
the construction_project_identity DB table is not seeded):
- pilot set + Procore id/name from `procore_projects.seed.yaml`
  (`load_procore_projects`, status == "pilot");
- HB project number + normalized name from `sharepoint_onedrive_sources.seed.yaml`
  (`load_source_registry`, `ProjectIdentity`).
"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel

from hb_assistant.construction.config.loader import load_source_registry
from hb_assistant.normalize.redaction import hash_value
from hb_assistant.procore.loader import load_procore_projects

# HB project number pattern, e.g. "23-435-01" (per the discovery policy).
HB_PROJECT_NUMBER_RE = re.compile(r"\b\d{2}-\d{3}-\d{2}\b")

# Procore notification sender domains (read-only signal, not a mutation surface).
_PROCORE_DOMAINS = ("procore.com", "procoretech.com", "mail.procore.com")

# Signal weights (name -> (confidence, review_required)) — package bands.
PROJECT_MATCH_SIGNALS: dict[str, tuple[float, bool]] = {
    "hb_project_number_in_subject": (1.00, False),
    "hb_project_number_in_body_preview": (0.95, True),
    "sharepoint_or_onedrive_project_link": (0.90, False),
    "procore_notification_identifier": (0.85, False),
    "project_name_in_subject": (0.80, False),
    "project_name_in_body_preview": (0.70, True),
    "known_participant_domain_contact": (0.60, True),
    "thread_continuation": (0.75, False),
}

# A match at or above this confidence is an accepted project match.
ACCEPT_THRESHOLD = 0.60


class ProjectDescriptor(BaseModel):
    """Matchable identity for one pilot project (no secrets)."""

    project_key: str
    project_number: Optional[str] = None
    display_name: Optional[str] = None
    project_name_normalized: Optional[str] = None
    procore_project_id: Optional[str] = None
    procore_project_name: Optional[str] = None
    known_domains: list[str] = []

    model_config = {"extra": "forbid"}

    def name_tokens(self) -> list[str]:
        """Distinct lowercased name strings to match (display + procore + normalized)."""
        raw = [self.display_name, self.procore_project_name]
        toks: list[str] = []
        for value in raw:
            if value:
                cleaned = value.strip().lower()
                if cleaned and cleaned not in toks:
                    toks.append(cleaned)
        if self.project_name_normalized:
            spaced = self.project_name_normalized.replace("_", " ").strip().lower()
            if spaced and spaced not in toks:
                toks.append(spaced)
        return toks


class MatchSignal(BaseModel):
    """One project-match signal fired for a message."""

    name: str
    confidence: float
    review_required: bool
    evidence_redacted: str
    match_value_hash: Optional[str] = None

    model_config = {"extra": "forbid"}


def _signal(name: str, evidence: str, match_value: Optional[str]) -> MatchSignal:
    confidence, review_required = PROJECT_MATCH_SIGNALS[name]
    return MatchSignal(
        name=name,
        confidence=confidence,
        review_required=review_required,
        evidence_redacted=evidence,
        match_value_hash=hash_value(match_value) if match_value else None,
    )


def _contains_number(text: Optional[str], project_number: Optional[str]) -> bool:
    if not text or not project_number:
        return False
    return any(m == project_number for m in HB_PROJECT_NUMBER_RE.findall(text))


def _contains_name(text: Optional[str], tokens: list[str]) -> Optional[str]:
    if not text:
        return None
    low = text.lower()
    for tok in tokens:
        # Word-boundary match to avoid loose substring false positives.
        if re.search(rf"\b{re.escape(tok)}\b", low):
            return tok
    return None


def _looks_like_project_link(text: Optional[str], descriptor: ProjectDescriptor) -> bool:
    if not text:
        return False
    low = text.lower()
    if "sharepoint.com" not in low and "-my.sharepoint.com" not in low and "onedrive" not in low:
        return False
    tokens = descriptor.name_tokens()
    if descriptor.project_number:
        tokens = tokens + [descriptor.project_number.lower()]
    if descriptor.project_name_normalized:
        tokens = tokens + [descriptor.project_name_normalized.lower()]
    return any(t and t in low for t in tokens)


class ProjectMatcher:
    """Deterministic project matcher (pure)."""

    def match(
        self,
        *,
        subject: Optional[str],
        body_preview: Optional[str],
        sender_domain: Optional[str],
        participant_domains: Optional[list[str]] = None,
        web_link: Optional[str] = None,
        descriptor: ProjectDescriptor,
    ) -> list[MatchSignal]:
        signals: list[MatchSignal] = []
        domains = [d.lower() for d in (participant_domains or []) if d]
        if sender_domain:
            domains.append(sender_domain.lower())

        # 1.00 — exact HB project number in subject
        if _contains_number(subject, descriptor.project_number):
            signals.append(
                _signal(
                    "hb_project_number_in_subject",
                    "project number in subject",
                    descriptor.project_number,
                )
            )
        # 0.95 — exact HB project number in bodyPreview
        elif _contains_number(body_preview, descriptor.project_number):
            signals.append(
                _signal(
                    "hb_project_number_in_body_preview",
                    "project number in body preview",
                    descriptor.project_number,
                )
            )

        # 0.90 — project-specific SharePoint/OneDrive link
        if _looks_like_project_link(web_link, descriptor) or _looks_like_project_link(
            body_preview, descriptor
        ):
            signals.append(
                _signal(
                    "sharepoint_or_onedrive_project_link",
                    "project sharepoint/onedrive link",
                    descriptor.project_key,
                )
            )

        # 0.85 — Procore notification with known project id/name
        if any(d == pd or d.endswith("." + pd) for d in domains for pd in _PROCORE_DOMAINS):
            haystack = f"{subject or ''}\n{body_preview or ''}"
            pid = descriptor.procore_project_id
            name_hit = _contains_name(haystack, descriptor.name_tokens())
            if (pid and pid in haystack) or name_hit:
                signals.append(
                    _signal(
                        "procore_notification_identifier",
                        "procore notification + project id/name",
                        pid or name_hit,
                    )
                )

        # 0.80 / 0.70 — project name in subject / bodyPreview
        name_in_subject = _contains_name(subject, descriptor.name_tokens())
        if name_in_subject:
            signals.append(
                _signal("project_name_in_subject", "project name in subject", name_in_subject)
            )
        else:
            name_in_preview = _contains_name(body_preview, descriptor.name_tokens())
            if name_in_preview:
                signals.append(
                    _signal(
                        "project_name_in_body_preview",
                        "project name in body preview",
                        name_in_preview,
                    )
                )

        # 0.60 — known participant domain/contact (inert until known_domains configured)
        known = {d.lower() for d in descriptor.known_domains}
        domain_hit = next((d for d in domains if d in known), None)
        if domain_hit:
            signals.append(
                _signal(
                    "known_participant_domain_contact",
                    "known project participant domain",
                    domain_hit,
                )
            )

        return signals


def thread_continuation_signal() -> MatchSignal:
    """The 0.75 signal applied to messages sharing a thread with a matched message."""
    return _signal("thread_continuation", "thread continuation from a matched message", None)


def load_pilot_project_descriptors(project_key: Optional[str] = None) -> list[ProjectDescriptor]:
    """Build pilot-project descriptors by merging the Procore + SharePoint seed registries.

    If ``project_key`` is given, restrict to that project (must be a known pilot).
    """
    procore = load_procore_projects()
    sources = load_source_registry()
    source_by_key = {p.project_key: p for p in sources.projects}

    descriptors: list[ProjectDescriptor] = []
    for mapping in procore.projects:
        if mapping.status != "pilot":
            continue
        key = mapping.hb_project_key
        if project_key is not None and key != project_key:
            continue
        src = source_by_key.get(key)
        descriptors.append(
            ProjectDescriptor(
                project_key=key,
                project_number=getattr(src, "project_number", None),
                display_name=getattr(src, "display_name", None),
                project_name_normalized=getattr(src, "project_name_normalized", None),
                procore_project_id=mapping.procore_project_id or None,
                procore_project_name=mapping.procore_project_name or None,
                known_domains=[],
            )
        )
    return descriptors
