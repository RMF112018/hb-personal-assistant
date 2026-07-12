"""Narrow, bounded, read-only content provider for indexed NAS source-root files (N8C-12E).

Given a stable ``source_id`` it resolves EXACTLY ONE configured file and returns a bounded, extension-gated
excerpt. It never walks, globs, recurses, scans a root, refreshes an index, generates a card, or mutates
anything — a single ``stat`` + single ``open`` via the SAME deterministic extractor the indexer uses.

Safety, in order (any failure degrades to the indexed excerpt, never an error/leak):
* the source must exist in the index (``get_source_detail``);
* its ``source_root_key`` must map to an ``enabled`` configured root;
* **sensitive roots are never live-read** (no existing policy grants it) — indexed excerpt only;
* the rel_path must pass the shared vault-safety rules (no protected/hidden segment, no ``..`` escape,
  no symlink escaping the root) and stay contained under the configured root;
* the extension must be in ``config.allowed_file_types`` (unsupported binaries are denied, not dumped);
* the file must exist and be within ``config.max_file_mb``.

Absolute host paths are NEVER returned. Fallback content is always labelled ``indexed_excerpt_fallback``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import pathsafe
from .config import ExternalSourceRoot, ObsidianMcpConfig
from .source_connector_models import (
    CONTENT_INDEXED_FALLBACK,
    CONTENT_LIVE_EXTRACT,
    READ_DEFAULT_CHARS,
    READ_MAX_CHARS,
    SourceConnectorValidationError,
    encode_source_ref,
    mime_for_ext,
)
from .source_index_repository import SourceIndexRepository

_LIVE_TEXT_EXTS = {"md", "markdown", "txt", "pdf", "docx", "xlsx", "eml"}


def _clamp_read_chars(max_chars: int | None) -> int:
    try:
        value = int(max_chars) if max_chars is not None else READ_DEFAULT_CHARS
    except (TypeError, ValueError):
        value = READ_DEFAULT_CHARS
    return max(1, min(value, READ_MAX_CHARS))


class SourceContentProvider:
    """Resolve + bounded-read a single indexed source file, with an indexed-excerpt fallback."""

    def __init__(self, repo: SourceIndexRepository, config: ObsidianMcpConfig) -> None:
        self._repo = repo
        self._config = config

    def _root_for(self, source_root_key: str | None) -> ExternalSourceRoot | None:
        if not source_root_key:
            return None
        for root in self._config.external_sources:
            if root.source_root_key == source_root_key and root.enabled:
                return root
        return None

    def _base(self, detail: dict[str, Any], source_id: str) -> dict[str, Any]:
        ext = (str(detail.get("file_ext")).lower().lstrip(".") if detail.get("file_ext") else None)
        return {
            "source_id": source_id,
            "source_ref": encode_source_ref(source_id),
            "source_root_key": detail.get("source_root_key"),
            "rel_path": detail.get("rel_path"),
            "extension": ext,
            "mime_type": mime_for_ext(ext),
        }

    def _indexed(self, detail: dict[str, Any], source_id: str, max_chars: int,
                 reason: str) -> dict[str, Any]:
        excerpt = detail.get("text_excerpt")
        available = excerpt is not None
        text = (str(excerpt)[:max_chars] if available else None)
        return {
            **self._base(detail, source_id),
            "content": text,
            "char_count": (len(text) if text is not None else 0),
            "content_source": CONTENT_INDEXED_FALLBACK if available else None,
            "truncated": bool(available and len(str(excerpt)) > max_chars)
                         or bool(detail.get("excerpt_truncated")),
            "extraction_status": detail.get("extraction_status"),
            "denied": not available,
            "reason": reason,
        }

    def read(self, source_id: str, *, max_chars: int | None = None, prefer_live: bool = True,
             conn: Any = None) -> dict[str, Any]:
        """Bounded read for one source. Returns live extract when policy allows, else the indexed
        excerpt (labelled ``indexed_excerpt_fallback``). Raises only when the source_id is unknown."""
        cap = _clamp_read_chars(max_chars)
        detail = self._repo.get_source_detail(source_id, conn=conn)
        if detail is None:
            raise SourceConnectorValidationError("source_not_found")

        ext = (str(detail.get("file_ext")).lower().lstrip(".") if detail.get("file_ext") else None)
        rel_path = detail.get("rel_path")
        root = self._root_for(detail.get("source_root_key"))

        if not prefer_live:
            return self._indexed(detail, source_id, cap, "indexed_requested")
        if detail.get("deleted"):
            return self._indexed(detail, source_id, cap, "source_deleted")
        if root is None:
            return self._indexed(detail, source_id, cap, "root_unavailable")
        if root.sensitive:
            return self._indexed(detail, source_id, cap, "sensitive_root")
        if not rel_path:
            return self._indexed(detail, source_id, cap, "no_rel_path")
        if pathsafe.path_blocked(str(rel_path), include_hidden=False) or \
                pathsafe.has_protected_segment(str(rel_path)):
            return self._indexed(detail, source_id, cap, "blocked_path")
        allowed = {str(e).lower().lstrip(".") for e in self._config.allowed_file_types}
        if not ext or ext not in allowed or ext not in _LIVE_TEXT_EXTS:
            return self._indexed(detail, source_id, cap, "unsupported_type")

        # A2: evaluate root trust BEFORE any live filesystem access. An untrusted root (policy
        # uncertified/stale, index unready, unverified/denied authorization) can never be live-read — fall
        # back to the bounded indexed excerpt with the sanitized readiness envelope.
        from .source_root_trust import load_root_trust, root_readiness_envelope

        _decision = load_root_trust(
            self._repo, self._config, None, str(detail.get("source_root_key")), conn=conn
        )
        if not _decision.safe_for_live_read:
            blocked = self._indexed(detail, source_id, cap, "root_not_trusted")
            blocked["root_readiness"] = root_readiness_envelope(_decision)
            return blocked

        root_resolved = Path(root.path).resolve()
        abs_path = Path(root.path) / str(rel_path)
        try:
            abs_path.resolve().relative_to(root_resolved)
        except ValueError:
            return self._indexed(detail, source_id, cap, "path_escape")
        if pathsafe.symlink_escapes(abs_path, root_resolved):
            return self._indexed(detail, source_id, cap, "symlink_escape")
        if not abs_path.is_file():
            return self._indexed(detail, source_id, cap, "file_absent")
        try:
            size = abs_path.stat().st_size
        except OSError:
            return self._indexed(detail, source_id, cap, "stat_failed")
        if size > int(self._config.max_file_mb) * 1024 * 1024:
            return self._indexed(detail, source_id, cap, "file_too_large")

        from .source_indexer import _extract  # lazy: pulls parser imports only on a live read

        # Ask the extractor for one extra char so a bounded result's ``truncated`` flag is exact
        # (the extractor itself hard-truncates to its ``max_chars`` argument).
        extracted = _extract(abs_path, ext, cap + 1)
        text = extracted.get("text_excerpt")
        if text is None or extracted.get("extraction_status") not in ("ok", "partial"):
            return self._indexed(detail, source_id, cap, "extraction_unavailable")
        bounded = str(text)[:cap]
        return {
            **self._base(detail, source_id),
            "content": bounded,
            "char_count": len(bounded),
            "content_source": CONTENT_LIVE_EXTRACT,
            "truncated": len(str(text)) > cap,
            "extraction_status": extracted.get("extraction_status"),
            "denied": False,
            "reason": None,
        }
