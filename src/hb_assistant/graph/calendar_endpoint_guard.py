"""Phase 07B — Microsoft Graph calendar read-only endpoint guard.

Runtime enforcement of the Phase 07B calendar endpoint contract: every calendar
request must be a GET against an allowlisted read pattern, and any calendar-
mutating verb, path, or operation keyword (event create/update/delete, attendee
accept/decline/tentative response, organizer cancel, forward, reminder snooze/
dismiss) is refused **before** an HTTP request is issued.

This is the HTTP layer of the calendar read-only defense-in-depth, mirroring
``mail_endpoint_guard.py`` / ``files_endpoint_guard.py``. The forbidden verbs,
paths, and keywords are loaded from the static contract resources in
``resources/config/`` — they are deliberately **not** hard-coded here so this
module stays free of literal mutation-endpoint strings (which the
``test_mutation_lockout`` static scan forbids in ``graph/``).

Decision order is positive-allowlist-first: a GET against an allowlisted template
is allowed immediately, so a legitimate calendar/event read can never false-
positive on a forbidden operation keyword. Anything that is not an allowlisted GET
is then blocked, with the most specific available reason.

Permission tightening is DEFERRED for this phase: the tenant still consents the
write-capable ``Calendars.ReadWrite.Shared`` scope. This guard constrains
*behavior* to read-only regardless of the granted scopes. It does not change or
inspect scopes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

from hb_assistant.config.path_policy import PathPolicy

_GRAPH_ROOTS = (
    "https://graph.microsoft.com/v1.0",
    "https://graph.microsoft.com/beta",
)


class CalendarMutationBlockedError(Exception):
    """Raised before any HTTP call when a calendar request is not a read-only GET.

    Sanitized: carries only the HTTP method, the normalized path, and a short
    reason — never tokens, headers, event bodies, join URLs, or attendee details.
    """

    def __init__(self, method: str, path: str, reason: str) -> None:
        self.method = method
        self.path = path
        self.reason = reason
        super().__init__(f"{method} {path} blocked: {reason}")


@dataclass(frozen=True)
class CalendarEndpointContract:
    """Parsed view of the read allowlist + mutation blocklist YAML resources."""

    allowed_methods: frozenset[str]
    allowed_paths: tuple[str, ...]
    forbidden_methods: frozenset[str]
    forbidden_paths: tuple[str, ...]
    forbidden_operation_keywords: tuple[str, ...]
    event_metadata_select: tuple[str, ...]


def _config_dir() -> Path:
    return PathPolicy().resolve_repo_root() / "resources" / "config"


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a top-level mapping")
    return data


_CONTRACT: Optional[CalendarEndpointContract] = None


def load_calendar_endpoint_contract(*, refresh: bool = False) -> CalendarEndpointContract:
    """Load and cache the Graph calendar read allowlist + mutation blocklist."""
    global _CONTRACT
    if _CONTRACT is not None and not refresh:
        return _CONTRACT

    config_dir = _config_dir()
    allow = _load_yaml(config_dir / "graph_calendar_read_endpoint_allowlist.yaml")
    block = _load_yaml(config_dir / "graph_calendar_mutation_endpoint_blocklist.yaml")

    contract = CalendarEndpointContract(
        allowed_methods=frozenset(m.upper() for m in allow.get("allowed_methods", [])),
        allowed_paths=tuple(allow.get("allowed_paths", [])),
        forbidden_methods=frozenset(m.upper() for m in block.get("forbidden_methods", [])),
        forbidden_paths=tuple(block.get("forbidden_paths", [])),
        forbidden_operation_keywords=tuple(block.get("forbidden_operation_keywords", [])),
        event_metadata_select=tuple(allow.get("event_metadata_select", [])),
    )
    _CONTRACT = contract
    return contract


def _normalize_path(path: str) -> str:
    """Reduce a request path to a leading-slash, query-free, root-free form."""
    p = path.strip()
    for root in _GRAPH_ROOTS:
        if p.startswith(root):
            p = p[len(root):]
            break
    # Drop any scheme://host that is not a known Graph root (defensive).
    if "://" in p:
        p = "/" + p.split("://", 1)[1].split("/", 1)[-1]
    p = p.split("?", 1)[0].split("#", 1)[0]
    if not p.startswith("/"):
        p = "/" + p
    if len(p) > 1:
        p = p.rstrip("/")
    return p


def _segments(path: str) -> list[str]:
    return [seg for seg in path.split("/") if seg]


def _matches_template(path: str, template: str) -> bool:
    """Structural match: equal segment count; literal segments compared
    case-insensitively; ``{placeholder}`` segments match any single segment."""
    p_segs = _segments(path)
    t_segs = _segments(template)
    if len(p_segs) != len(t_segs):
        return False
    for p_seg, t_seg in zip(p_segs, t_segs, strict=True):
        if t_seg.startswith("{") and t_seg.endswith("}"):
            continue
        if p_seg.lower() != t_seg.lower():
            return False
    return True


def _matches_any_template(path: str, templates: tuple[str, ...]) -> bool:
    return any(_matches_template(path, t) for t in templates)


def _forbidden_keyword_hit(path: str, keywords: tuple[str, ...]) -> Optional[str]:
    """Return the first path *segment* that contains a forbidden operation
    keyword (case-insensitive). Only applied to non-allowlisted paths, so
    legitimate calendar/event reads are never inspected here."""
    for seg in _segments(path):
        low = seg.lower()
        for kw in keywords:
            if kw.lower() in low:
                return seg
    return None


def sample_path(template: str) -> str:
    """Fill ``{placeholder}`` segments with a sample id (for guard self-testing).
    Literal segments are preserved."""
    return "/".join(
        "SAMPLEID" if seg.startswith("{") and seg.endswith("}") else seg
        for seg in template.split("/")
    )


def assert_calendar_request_allowed(
    method: str, path: str, *, contract: Optional[CalendarEndpointContract] = None
) -> None:
    """Raise ``CalendarMutationBlockedError`` unless ``method``/``path`` is an
    allowlisted read-only GET. Returns ``None`` when the request is permitted.

    Call this before issuing any Graph calendar HTTP request.
    """
    c = contract or load_calendar_endpoint_contract()
    m = method.upper()
    norm = _normalize_path(path)

    # Positive allowlist first: a GET against an allowlisted read template is
    # permitted outright (no keyword inspection of calendar/event ids).
    if m in c.allowed_methods and _matches_any_template(norm, c.allowed_paths):
        return None

    # Otherwise blocked — surface the most specific reason.
    if m in c.forbidden_methods:
        raise CalendarMutationBlockedError(m, norm, f"HTTP method {m} is a forbidden calendar-mutation verb")
    if m not in c.allowed_methods:
        raise CalendarMutationBlockedError(m, norm, f"HTTP method {m} is not in the GET-only read allowlist")
    if _matches_any_template(norm, c.forbidden_paths):
        raise CalendarMutationBlockedError(m, norm, "path matches a forbidden calendar-mutation endpoint")
    hit = _forbidden_keyword_hit(norm, c.forbidden_operation_keywords)
    if hit is not None:
        raise CalendarMutationBlockedError(m, norm, f"path segment {hit!r} is a forbidden calendar operation")
    raise CalendarMutationBlockedError(m, norm, "path is not on the read allowlist")


def run_calendar_no_writeback_self_test(
    contract: Optional[CalendarEndpointContract] = None,
) -> dict[str, Any]:
    """Prove, in-process and without network, that the guard allows every
    allowlisted GET and blocks every forbidden verb/path. Deterministic."""
    c = contract or load_calendar_endpoint_contract()
    anomalies: list[str] = []
    read_allowed = 0
    mutation_blocked = 0

    for tmpl in c.allowed_paths:
        try:
            assert_calendar_request_allowed("GET", sample_path(tmpl), contract=c)
            read_allowed += 1
        except CalendarMutationBlockedError as e:
            anomalies.append(f"GET {tmpl} unexpectedly blocked: {e.reason}")

    for tmpl in c.forbidden_paths:
        try:
            assert_calendar_request_allowed("POST", sample_path(tmpl), contract=c)
            anomalies.append(f"POST {tmpl} unexpectedly allowed")
        except CalendarMutationBlockedError:
            mutation_blocked += 1

    # Each forbidden verb must be blocked even on an otherwise GET-readable event.
    for verb in sorted(c.forbidden_methods):
        try:
            assert_calendar_request_allowed(verb, "/me/events/SAMPLEID", contract=c)
            anomalies.append(f"{verb} on a readable event path unexpectedly allowed")
        except CalendarMutationBlockedError:
            mutation_blocked += 1

    return {
        "passed": not anomalies,
        "read_paths_allowed": read_allowed,
        "mutation_attempts_blocked": mutation_blocked,
        "anomalies": anomalies,
    }
