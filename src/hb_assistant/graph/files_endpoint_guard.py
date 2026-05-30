"""Phase 06 (Files) — Microsoft Graph SharePoint/OneDrive read-only endpoint guard.

Runtime enforcement of the Prompt 01 file endpoint contract: every drive/site/
driveItem request must be a GET against an allowlisted read pattern, and any
file-mutating verb, path, or operation keyword (upload, create, delete, move,
copy, share, checkout/checkin, permission/label change, upload session) is
refused **before** an HTTP request is issued.

This is the HTTP layer of the Phase 06 (Files) defense-in-depth, mirroring
``mail_endpoint_guard.py``. The forbidden verbs, paths, and keywords are loaded
from the static contract resources in ``resources/config/`` — they are
deliberately **not** hard-coded here so this module stays free of literal
mutation-endpoint strings (which the ``test_mutation_lockout`` static scan
forbids in ``graph/``).

Decision order is positive-allowlist-first: a GET against an allowlisted template
is allowed immediately, so a legitimate folder/item read can never false-positive
on a forbidden operation keyword. Anything that is not an allowlisted GET is then
blocked, with the most specific available reason.

Permission tightening is DEFERRED for this phase: the tenant still consents broad
write-capable scopes. This guard constrains *behavior* to read-only regardless of
the granted scopes. It does not change or inspect scopes.
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


class FileMutationBlockedError(Exception):
    """Raised before any HTTP call when a file request is not a read-only GET.

    Sanitized: carries only the HTTP method, the normalized path, and a short
    reason — never tokens, headers, signed URLs, or document content.
    """

    def __init__(self, method: str, path: str, reason: str) -> None:
        self.method = method
        self.path = path
        self.reason = reason
        super().__init__(f"{method} {path} blocked: {reason}")


@dataclass(frozen=True)
class FilesEndpointContract:
    """Parsed view of the read allowlist + mutation blocklist + metadata YAML."""

    allowed_methods: frozenset[str]
    allowed_paths: tuple[str, ...]
    forbidden_methods: frozenset[str]
    forbidden_paths: tuple[str, ...]
    forbidden_operation_keywords: tuple[str, ...]
    drive_item_metadata_select: tuple[str, ...]
    never_persist: tuple[str, ...]


def _config_dir() -> Path:
    return PathPolicy().resolve_repo_root() / "resources" / "config"


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a top-level mapping")
    return data


def _paths(entries: Any) -> tuple[str, ...]:
    """Extract path strings from a YAML list that may hold either plain strings
    or mappings of the form ``{path: ..., provenance/operation: ...}``."""
    out: list[str] = []
    for e in entries or []:
        if isinstance(e, str):
            out.append(e)
        elif isinstance(e, dict) and isinstance(e.get("path"), str):
            out.append(e["path"])
    return tuple(out)


_CONTRACT: Optional[FilesEndpointContract] = None


def load_files_endpoint_contract(*, refresh: bool = False) -> FilesEndpointContract:
    """Load and cache the Graph files read allowlist + mutation blocklist +
    driveItem metadata field contract authored in Phase 06 (Files) Prompt 01."""
    global _CONTRACT
    if _CONTRACT is not None and not refresh:
        return _CONTRACT

    config_dir = _config_dir()
    allow = _load_yaml(config_dir / "graph_files_read_endpoint_allowlist.yaml")
    block = _load_yaml(config_dir / "graph_files_mutation_endpoint_blocklist.yaml")
    meta = _load_yaml(config_dir / "graph_files_drive_item_metadata_field_contract.yaml")

    contract = FilesEndpointContract(
        allowed_methods=frozenset(m.upper() for m in allow.get("allowed_methods", [])),
        allowed_paths=_paths(allow.get("allowed_paths")),
        forbidden_methods=frozenset(m.upper() for m in block.get("forbidden_methods", [])),
        forbidden_paths=_paths(block.get("forbidden_paths")),
        forbidden_operation_keywords=tuple(block.get("forbidden_operation_keywords", [])),
        drive_item_metadata_select=tuple(allow.get("drive_item_metadata_select", [])),
        never_persist=tuple(meta.get("never_persist", [])),
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


def _is_wildcard(segment: str) -> bool:
    """A template segment is a wildcard if it carries a ``{placeholder}`` token.
    This also covers colon-addressed segments such as ``{hostname}:`` and
    ``root:`` path templates used for SharePoint URL/path resolution."""
    return "{" in segment and "}" in segment


def _matches_template(path: str, template: str) -> bool:
    """Structural match: equal segment count; literal segments compared
    case-insensitively; ``{placeholder}``-bearing segments match any segment."""
    p_segs = _segments(path)
    t_segs = _segments(template)
    if len(p_segs) != len(t_segs):
        return False
    for p_seg, t_seg in zip(p_segs, t_segs, strict=True):
        if _is_wildcard(t_seg):
            continue
        if p_seg.lower() != t_seg.lower():
            return False
    return True


def _matches_any_template(path: str, templates: tuple[str, ...]) -> bool:
    return any(_matches_template(path, t) for t in templates)


def _forbidden_keyword_hit(path: str, keywords: tuple[str, ...]) -> Optional[str]:
    """Return the first path *segment* that contains a forbidden operation
    keyword (case-insensitive). Only applied to non-allowlisted paths, so
    legitimate folder/item reads are never inspected here."""
    for seg in _segments(path):
        low = seg.lower()
        for kw in keywords:
            if kw.lower() in low:
                return seg
    return None


def sample_path(template: str) -> str:
    """Fill ``{placeholder}``-bearing segments with a sample id (for guard
    self-testing and contract documentation). Literal segments are preserved."""
    return "/".join(
        "SAMPLEID" if _is_wildcard(seg) else seg
        for seg in template.split("/")
    )


def assert_files_request_allowed(
    method: str, path: str, *, contract: Optional[FilesEndpointContract] = None
) -> None:
    """Raise ``FileMutationBlockedError`` unless ``method``/``path`` is an
    allowlisted read-only GET. Returns ``None`` when the request is permitted.

    Call this before issuing any Graph SharePoint/OneDrive file HTTP request.
    """
    c = contract or load_files_endpoint_contract()
    m = method.upper()
    norm = _normalize_path(path)

    # Positive allowlist first: a GET against an allowlisted read template is
    # permitted outright (no keyword inspection of folder ids / names).
    if m in c.allowed_methods and _matches_any_template(norm, c.allowed_paths):
        return None

    # Otherwise blocked — surface the most specific reason.
    if m in c.forbidden_methods:
        raise FileMutationBlockedError(m, norm, f"HTTP method {m} is a forbidden file-mutation verb")
    if m not in c.allowed_methods:
        raise FileMutationBlockedError(m, norm, f"HTTP method {m} is not in the GET-only read allowlist")
    if _matches_any_template(norm, c.forbidden_paths):
        raise FileMutationBlockedError(m, norm, "path matches a forbidden file-mutation endpoint")
    hit = _forbidden_keyword_hit(norm, c.forbidden_operation_keywords)
    if hit is not None:
        raise FileMutationBlockedError(m, norm, f"path segment {hit!r} is a forbidden file operation")
    raise FileMutationBlockedError(m, norm, "path is not on the read allowlist")


def run_files_no_writeback_self_test(
    contract: Optional[FilesEndpointContract] = None,
) -> dict[str, Any]:
    """Prove, in-process and without network, that the guard allows every
    allowlisted GET and blocks every forbidden verb/path. Deterministic."""
    c = contract or load_files_endpoint_contract()
    anomalies: list[str] = []
    read_allowed = 0
    mutation_blocked = 0

    for tmpl in c.allowed_paths:
        try:
            assert_files_request_allowed("GET", sample_path(tmpl), contract=c)
            read_allowed += 1
        except FileMutationBlockedError as e:
            anomalies.append(f"GET {tmpl} unexpectedly blocked: {e.reason}")

    for tmpl in c.forbidden_paths:
        try:
            assert_files_request_allowed("POST", sample_path(tmpl), contract=c)
            anomalies.append(f"POST {tmpl} unexpectedly allowed")
        except FileMutationBlockedError:
            mutation_blocked += 1

    for verb in sorted(c.forbidden_methods):
        try:
            assert_files_request_allowed(verb, "/drives/SAMPLEID/items/SAMPLEID", contract=c)
            anomalies.append(f"{verb} on an allowlisted path unexpectedly allowed")
        except FileMutationBlockedError:
            mutation_blocked += 1

    return {
        "passed": not anomalies,
        "read_paths_allowed": read_allowed,
        "mutation_attempts_blocked": mutation_blocked,
        "anomalies": anomalies,
    }
