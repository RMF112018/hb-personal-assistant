"""Phase 06 — Microsoft Graph mailbox read-only endpoint guard.

Runtime enforcement of the Prompt 01 endpoint contract: every mail request must
be a GET against an allowlisted read pattern, and any mailbox-mutating verb,
path, or operation keyword is refused **before** an HTTP request is issued.

This is the HTTP layer of the Phase 06 defense-in-depth (atop the Pydantic model,
store-adapter, SQLite CHECK, and MSAL scope layers). The forbidden verbs, paths,
and keywords are loaded from the static contract resources in
``resources/config/`` — they are deliberately **not** hard-coded here so this
module stays free of literal mutation-endpoint strings (which the
``test_mutation_lockout`` static scan forbids in ``graph/``).

Decision order is positive-allowlist-first: a GET against an allowlisted template
is allowed immediately, so a legitimate folder read (even a well-known folder
addressed by name, e.g. ``drafts``) can never false-positive on a forbidden
operation keyword. Anything that is not an allowlisted GET is then blocked, with
the most specific available reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from hb_assistant.config.path_policy import PathPolicy

_GRAPH_ROOTS = (
    "https://graph.microsoft.com/v1.0",
    "https://graph.microsoft.com/beta",
)


class MailboxMutationBlockedError(Exception):
    """Raised before any HTTP call when a mail request is not a read-only GET.

    Sanitized: carries only the HTTP method, the normalized path, and a short
    reason — never tokens, headers, or message content.
    """

    def __init__(self, method: str, path: str, reason: str) -> None:
        self.method = method
        self.path = path
        self.reason = reason
        super().__init__(f"{method} {path} blocked: {reason}")


@dataclass(frozen=True)
class MailEndpointContract:
    """Parsed view of the read allowlist + mutation blocklist YAML resources."""

    allowed_methods: frozenset[str]
    allowed_paths: tuple[str, ...]
    forbidden_methods: frozenset[str]
    forbidden_paths: tuple[str, ...]
    forbidden_operation_keywords: tuple[str, ...]
    message_metadata_select: tuple[str, ...]
    attachment_metadata_select: tuple[str, ...]


def _config_dir() -> Path:
    return PathPolicy().resolve_repo_root() / "resources" / "config"


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a top-level mapping")
    return data


_CONTRACT: Optional[MailEndpointContract] = None


def load_mail_endpoint_contract(*, refresh: bool = False) -> MailEndpointContract:
    """Load and cache the Graph mail read allowlist + mutation blocklist.

    Reads the repo-native YAML contract authored in Phase 06 Prompt 01.
    """
    global _CONTRACT
    if _CONTRACT is not None and not refresh:
        return _CONTRACT

    config_dir = _config_dir()
    allow = _load_yaml(config_dir / "graph_mail_read_endpoint_allowlist.yaml")
    block = _load_yaml(config_dir / "graph_mail_mutation_endpoint_blocklist.yaml")

    contract = MailEndpointContract(
        allowed_methods=frozenset(m.upper() for m in allow.get("allowed_methods", [])),
        allowed_paths=tuple(allow.get("allowed_paths", [])),
        forbidden_methods=frozenset(m.upper() for m in block.get("forbidden_methods", [])),
        forbidden_paths=tuple(block.get("forbidden_paths", [])),
        forbidden_operation_keywords=tuple(block.get("forbidden_operation_keywords", [])),
        message_metadata_select=tuple(allow.get("message_metadata_select", [])),
        attachment_metadata_select=tuple(allow.get("attachment_metadata_select", [])),
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
    legitimate folder-name reads are never inspected here."""
    for seg in _segments(path):
        low = seg.lower()
        for kw in keywords:
            if kw.lower() in low:
                return seg
    return None


def assert_mail_request_allowed(method: str, path: str, *, contract: Optional[MailEndpointContract] = None) -> None:
    """Raise ``MailboxMutationBlockedError`` unless ``method``/``path`` is an
    allowlisted read-only GET. Returns ``None`` when the request is permitted.

    Call this before issuing any Graph mail HTTP request.
    """
    c = contract or load_mail_endpoint_contract()
    m = method.upper()
    norm = _normalize_path(path)

    # Positive allowlist first: a GET against an allowlisted read template is
    # permitted outright (no keyword inspection of folder ids / names).
    if m in c.allowed_methods and _matches_any_template(norm, c.allowed_paths):
        return None

    # Otherwise blocked — surface the most specific reason.
    if m in c.forbidden_methods:
        raise MailboxMutationBlockedError(m, norm, f"HTTP method {m} is a forbidden mailbox-mutation verb")
    if m not in c.allowed_methods:
        raise MailboxMutationBlockedError(m, norm, f"HTTP method {m} is not in the GET-only read allowlist")
    if _matches_any_template(norm, c.forbidden_paths):
        raise MailboxMutationBlockedError(m, norm, "path matches a forbidden mailbox-mutation endpoint")
    hit = _forbidden_keyword_hit(norm, c.forbidden_operation_keywords)
    if hit is not None:
        raise MailboxMutationBlockedError(m, norm, f"path segment {hit!r} is a forbidden mailbox operation")
    raise MailboxMutationBlockedError(m, norm, "path is not on the read allowlist")
