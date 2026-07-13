"""Narrow, bounded, read-only content provider for indexed NAS source-root files (N8C-12E / Phase B).

Given a stable ``source_id`` it resolves EXACTLY ONE configured file. Two client-facing modes:

* ``mode="excerpt"`` (default, unchanged N8C-12E behaviour): a bounded, extension-gated excerpt — live
  extract when policy allows, else the indexed excerpt (labelled ``indexed_excerpt_fallback``).
* ``mode="complete"`` (Phase B / B1): a *complete-or-explicit-failure* read. It NEVER truncates and
  labels the result complete; over-limit / unsupported / stale / parser-failure all return an explicit
  ``retrieval_state`` with ``content=None``. Complex formats (pdf/docx/xlsx/eml) are extracted in a
  subprocess-isolated, time/memory/output-bounded worker (``files/parsers/isolated``) so a hostile file
  can never stall or crash the MCP process. A pre/post-read ``stat`` guard and an index-divergence guard
  reject content that changed under us or that the index no longer matches.

Shared safety cascade (any failure never leaks an error/path): source must exist in the index; its
``source_root_key`` must map to an ``enabled`` root; sensitive roots are never live-read; the rel_path
must pass the vault-safety rules (no protected/hidden segment, no ``..``/symlink escape) and stay under
the root; the extension must be supported; the root must be trusted; the file must exist and be within
the size bounds. Absolute host paths are NEVER returned.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import pathsafe
from .config import ExternalSourceRoot, ObsidianMcpConfig
from .source_connector_models import (
    COMP_COMPLETE,
    COMP_NONE,
    COMP_PARTIAL,
    COMPLETE_READ_TEXT_EXTS,
    CONTENT_INDEXED_FALLBACK,
    CONTENT_LIVE_EXTRACT,
    CS_EXTRACTED,
    CS_METADATA_ONLY,
    CS_NONE,
    CS_RAW_TEXT,
    READ_DEFAULT_CHARS,
    READ_MAX_CHARS,
    READ_MODE_COMPLETE,
    READ_MODE_EXCERPT,
    RS_ARCHIVE_NOT_EXPANDED,
    RS_COMPLETE,
    RS_DENIED,
    RS_MOVED,
    RS_PARSER_FAILED,
    RS_PARSER_OUTPUT_TOO_LARGE,
    RS_PARSER_RESOURCE_EXCEEDED,
    RS_PARSER_TIMEOUT,
    RS_PARTIAL,
    RS_STALE,
    RS_TOO_LARGE,
    RS_UNAVAILABLE,
    RS_UNSUPPORTED,
    SourceConnectorValidationError,
    encode_source_ref,
    mime_for_ext,
)
from .source_index_repository import SourceIndexRepository

_LIVE_TEXT_EXTS = {"md", "markdown", "txt", "pdf", "docx", "xlsx", "eml"}

# Formats that a complete read can fully extract via the isolated worker.
_ISOLATED_PARSER_EXTS = {"pdf", "docx", "xlsx", "eml"}
# Explicitly-unsupported binaries that must return an honest "found but not interpretable" answer.
_SCHEDULE_BINARY_EXTS = {"xer", "mpp", "pln", "xml_p6"}
_ARCHIVE_EXTS = {"zip", "tar", "gz", "tgz", "7z", "rar"}

# Change detection matches the indexer's own currency contract (exact st_mtime_ns / st_size equality;
# see source_indexer.py fast-skip). Same file, same ns clock -> exact comparison is correct.

# excerpt-mode block reason -> retrieval_state (excerpt degrades to the indexed excerpt, so these are
# advisory classifications carried alongside the returned excerpt/metadata).
_EXCERPT_REASON_STATE = {
    "indexed_requested": RS_PARTIAL,
    "source_deleted": RS_UNAVAILABLE,
    "root_unavailable": RS_UNAVAILABLE,
    "no_rel_path": RS_UNAVAILABLE,
    "file_absent": RS_UNAVAILABLE,
    "stat_failed": RS_UNAVAILABLE,
    "sensitive_root": RS_DENIED,
    "blocked_path": RS_DENIED,
    "path_escape": RS_DENIED,
    "symlink_escape": RS_DENIED,
    "unsupported_type": RS_UNSUPPORTED,
    "root_not_trusted": RS_STALE,
    "file_too_large": RS_TOO_LARGE,
    "extraction_unavailable": RS_PARSER_FAILED,
}


def _clamp_read_chars(max_chars: int | None) -> int:
    try:
        value = int(max_chars) if max_chars is not None else READ_DEFAULT_CHARS
    except (TypeError, ValueError):
        value = READ_DEFAULT_CHARS
    return max(1, min(value, READ_MAX_CHARS))


class SourceContentProvider:
    """Resolve + read a single indexed source file (bounded excerpt or complete-or-fail)."""

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

    @staticmethod
    def _ext_of(detail: dict[str, Any]) -> str | None:
        return str(detail.get("file_ext")).lower().lstrip(".") if detail.get("file_ext") else None

    def _base(self, detail: dict[str, Any], source_id: str) -> dict[str, Any]:
        ext = self._ext_of(detail)
        return {
            "source_id": source_id,
            "source_ref": encode_source_ref(source_id),
            "source_root_key": detail.get("source_root_key"),
            "rel_path": detail.get("rel_path"),
            "extension": ext,
            "mime_type": mime_for_ext(ext),
        }

    # ------------------------------------------------------------------ provenance

    def _provenance(
        self,
        detail: dict[str, Any],
        source_id: str,
        *,
        retrieval_state: str,
        content_state: str,
        completeness_state: str,
        live_size: int | None = None,
        generation_status: str | None = None,
    ) -> dict[str, Any]:
        """Path-free provenance block (mirrors the authoritative top-level state fields)."""
        ext = self._ext_of(detail)
        rel_path = detail.get("rel_path")
        return {
            "source_ref": encode_source_ref(source_id),  # preferred client handoff
            "source_id": source_id,  # internal/compat metadata
            "root_key": detail.get("source_root_key"),
            "relative_path": rel_path,
            "filename": (Path(str(rel_path)).name if rel_path else None),
            "extension": ext,
            "mime_type": mime_for_ext(ext),
            "size_bytes": live_size if live_size is not None else detail.get("size_bytes"),
            "modified_at_ns": detail.get("mtime_ns"),
            "indexed_at": detail.get("indexed_at"),
            "generation_status": generation_status,
            "content_state": content_state,
            "retrieval_state": retrieval_state,
            "completeness_state": completeness_state,
        }

    # ------------------------------------------------------------------ excerpt mode (unchanged)

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

    def _annotate_excerpt_states(self, resp: dict[str, Any], detail: dict[str, Any],
                                 source_id: str) -> dict[str, Any]:
        """Add the Phase B state vocabulary to an excerpt response (advisory: excerpt is always a
        bounded, partial representation)."""
        ext = self._ext_of(detail)
        if resp.get("content") is not None:
            retrieval_state = RS_PARTIAL
            content_state = CS_EXTRACTED if ext in _ISOLATED_PARSER_EXTS else CS_RAW_TEXT
            completeness_state = COMP_PARTIAL
        else:
            retrieval_state = _EXCERPT_REASON_STATE.get(resp.get("reason"), RS_UNAVAILABLE)
            content_state = CS_METADATA_ONLY
            completeness_state = COMP_NONE
        resp["mode"] = READ_MODE_EXCERPT
        resp["retrieval_state"] = retrieval_state
        resp["content_state"] = content_state
        resp["completeness_state"] = completeness_state
        resp["provenance"] = self._provenance(
            detail, source_id, retrieval_state=retrieval_state,
            content_state=content_state, completeness_state=completeness_state,
        )
        return resp

    def _read_excerpt(self, source_id: str, detail: dict[str, Any], *, max_chars: int | None,
                      prefer_live: bool, conn: Any) -> dict[str, Any]:
        cap = _clamp_read_chars(max_chars)
        ext = self._ext_of(detail)
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

    # ------------------------------------------------------------------ complete mode (Phase B)

    def _effective_output_limit(self, max_bytes: int | None) -> int:
        server = int(self._config.source_complete_read_max_output_bytes)
        if max_bytes is None:
            return server
        try:
            requested = int(max_bytes)
        except (TypeError, ValueError):
            return server
        return max(1, min(server, requested))

    def _complete_blocked(self, detail: dict[str, Any], source_id: str, *, retrieval_state: str,
                          content_state: str, reason: str | None = None,
                          **extra: Any) -> dict[str, Any]:
        prov = self._provenance(
            detail, source_id, retrieval_state=retrieval_state,
            content_state=content_state, completeness_state=COMP_NONE,
            live_size=extra.get("size_bytes"),
        )
        return {
            **self._base(detail, source_id),
            "mode": READ_MODE_COMPLETE,
            "content": None,
            "char_count": 0,
            "content_source": None,
            "truncated": False,
            "retrieval_state": retrieval_state,
            "content_state": content_state,
            "completeness_state": COMP_NONE,
            "denied": retrieval_state == RS_DENIED,
            "reason": reason,
            "provenance": prov,
            **extra,
        }

    def _read_complete(self, source_id: str, detail: dict[str, Any], *, max_bytes: int | None,
                       conn: Any) -> dict[str, Any]:
        ext = self._ext_of(detail)
        rel_path = detail.get("rel_path")

        # NOTE (B4): a deleted row whose lineage names an authorized successor is answered `moved` by the
        # service layer BEFORE this method; here a deleted row is simply unavailable.
        if detail.get("deleted"):
            return self._complete_blocked(detail, source_id, retrieval_state=RS_UNAVAILABLE,
                                          content_state=CS_METADATA_ONLY, reason="source_deleted")
        root = self._root_for(detail.get("source_root_key"))
        if root is None:
            return self._complete_blocked(detail, source_id, retrieval_state=RS_UNAVAILABLE,
                                          content_state=CS_METADATA_ONLY, reason="root_unavailable")
        if root.sensitive:
            return self._complete_blocked(detail, source_id, retrieval_state=RS_DENIED,
                                          content_state=CS_METADATA_ONLY, reason="sensitive_root")
        if not rel_path:
            return self._complete_blocked(detail, source_id, retrieval_state=RS_UNAVAILABLE,
                                          content_state=CS_METADATA_ONLY, reason="no_rel_path")
        if pathsafe.path_blocked(str(rel_path), include_hidden=False) or \
                pathsafe.has_protected_segment(str(rel_path)):
            return self._complete_blocked(detail, source_id, retrieval_state=RS_DENIED,
                                          content_state=CS_METADATA_ONLY, reason="blocked_path")

        # Explicit format classification (honest non-support; no fake XER/archive interpretation).
        if not ext:
            return self._complete_blocked(detail, source_id, retrieval_state=RS_UNSUPPORTED,
                                          content_state=CS_METADATA_ONLY, reason="unknown_extension")
        if ext in _SCHEDULE_BINARY_EXTS:
            return self._complete_blocked(
                detail, source_id, retrieval_state=RS_UNSUPPORTED, content_state=CS_METADATA_ONLY,
                reason="schedule_binary_not_supported",
                recommended_next_action=(
                    "File found. Complete interpretation of scheduling binaries "
                    f"(.{ext}, e.g. XER/P6) is not supported; do not invent schedule content."
                ),
            )
        if ext in _ARCHIVE_EXTS:
            return self._complete_blocked(
                detail, source_id, retrieval_state=RS_ARCHIVE_NOT_EXPANDED,
                content_state=CS_METADATA_ONLY, reason="archive_not_expanded",
                recommended_next_action="Archive found; contents are not expanded. List/extract members out of band.",
            )
        is_text = ext in COMPLETE_READ_TEXT_EXTS
        is_parser = ext in _ISOLATED_PARSER_EXTS
        if not (is_text or is_parser):
            return self._complete_blocked(detail, source_id, retrieval_state=RS_UNSUPPORTED,
                                          content_state=CS_METADATA_ONLY, reason="unsupported_format")

        # Trust: a live complete read requires the root to be trusted for live reads (same gate the
        # excerpt live path uses; encodes policy currency, authorization, and index readiness).
        from .source_root_trust import load_root_trust, root_readiness_envelope

        decision = load_root_trust(
            self._repo, self._config, None, str(detail.get("source_root_key")), conn=conn
        )
        gen_status = getattr(decision, "policy_verification", None)
        if not decision.safe_for_live_read:
            blocked = self._complete_blocked(detail, source_id, retrieval_state=RS_STALE,
                                             content_state=CS_METADATA_ONLY, reason="root_not_trusted",
                                             generation_status=gen_status)
            blocked["root_readiness"] = root_readiness_envelope(decision)
            blocked["provenance"]["generation_status"] = gen_status
            return blocked

        root_resolved = Path(root.path).resolve()
        abs_path = Path(root.path) / str(rel_path)
        try:
            abs_path.resolve().relative_to(root_resolved)
        except ValueError:
            return self._complete_blocked(detail, source_id, retrieval_state=RS_DENIED,
                                          content_state=CS_METADATA_ONLY, reason="path_escape")
        if pathsafe.symlink_escapes(abs_path, root_resolved):
            return self._complete_blocked(detail, source_id, retrieval_state=RS_DENIED,
                                          content_state=CS_METADATA_ONLY, reason="symlink_escape")
        if not abs_path.is_file():
            return self._complete_blocked(detail, source_id, retrieval_state=RS_UNAVAILABLE,
                                          content_state=CS_METADATA_ONLY, reason="file_absent")
        try:
            st1 = abs_path.stat()
        except OSError:
            return self._complete_blocked(detail, source_id, retrieval_state=RS_UNAVAILABLE,
                                          content_state=CS_METADATA_ONLY, reason="stat_failed")

        # Index-divergence guard: if the live file no longer matches what we indexed, the index is stale
        # relative to disk -> we cannot certify a *trusted* complete read.
        if self._diverges_from_index(detail, st1):
            return self._complete_blocked(detail, source_id, retrieval_state=RS_STALE,
                                          content_state=CS_METADATA_ONLY, reason="index_metadata_stale",
                                          generation_status=gen_status, size_bytes=st1.st_size)

        if is_text:
            result = self._complete_text(abs_path, st1, max_bytes)
        else:
            result = self._complete_parser(abs_path, ext, max_bytes)

        # Change-during-read guard: only meaningful when the read itself succeeded.
        if result.get("retrieval_state") == RS_COMPLETE:
            try:
                st2 = abs_path.stat()
            except OSError:
                return self._complete_blocked(detail, source_id, retrieval_state=RS_UNAVAILABLE,
                                              content_state=CS_METADATA_ONLY, reason="stat_failed_post")
            if st1.st_size != st2.st_size or st1.st_mtime_ns != st2.st_mtime_ns:
                return self._complete_blocked(detail, source_id, retrieval_state=RS_STALE,
                                              content_state=CS_METADATA_ONLY, reason="changed_during_read",
                                              generation_status=gen_status)

        live_size = result.pop("_live_size", st1.st_size)
        prov = self._provenance(
            detail, source_id, retrieval_state=result["retrieval_state"],
            content_state=result["content_state"], completeness_state=result["completeness_state"],
            live_size=live_size, generation_status=gen_status,
        )
        return {
            **self._base(detail, source_id),
            "mode": READ_MODE_COMPLETE,
            "denied": result["retrieval_state"] == RS_DENIED,
            "provenance": prov,
            **result,
        }

    def _diverges_from_index(self, detail: dict[str, Any], st: Any) -> bool:
        idx_size = detail.get("size_bytes")
        idx_mtime = detail.get("mtime_ns")
        if idx_size is None and idx_mtime is None:
            return False  # nothing indexed to compare against
        if idx_size is not None and int(idx_size) != int(st.st_size):
            return True
        return idx_mtime is not None and int(idx_mtime) != int(st.st_mtime_ns)

    def _complete_text(self, abs_path: Path, st1: Any, max_bytes: int | None) -> dict[str, Any]:
        limit = self._effective_output_limit(max_bytes)
        # Input gate (text): a very large text file is rejected before we read it into memory.
        if int(st1.st_size) > int(self._config.source_complete_read_max_input_bytes):
            return {"content": None, "char_count": 0, "content_source": None, "truncated": False,
                    "retrieval_state": RS_TOO_LARGE, "content_state": CS_NONE,
                    "completeness_state": COMP_NONE, "reason": "input_too_large",
                    "_live_size": int(st1.st_size),
                    "recommended_next_action": "File too large for a complete read; use mode='excerpt'."}
        try:
            raw = abs_path.read_bytes()
        except OSError as exc:
            return {"content": None, "char_count": 0, "content_source": None, "truncated": False,
                    "retrieval_state": RS_UNAVAILABLE, "content_state": CS_METADATA_ONLY,
                    "completeness_state": COMP_NONE, "reason": type(exc).__name__}
        if len(raw) > limit:
            return {"content": None, "char_count": 0, "content_source": None, "truncated": False,
                    "retrieval_state": RS_TOO_LARGE, "content_state": CS_NONE,
                    "completeness_state": COMP_NONE, "reason": "output_too_large",
                    "_live_size": len(raw), "output_bytes_lower_bound": len(raw),
                    "recommended_next_action": "Extracted text exceeds the complete-read budget; use mode='excerpt'."}
        text = raw.decode("utf-8", errors="replace")
        return {"content": text, "char_count": len(text), "content_source": CONTENT_LIVE_EXTRACT,
                "truncated": False, "retrieval_state": RS_COMPLETE, "content_state": CS_RAW_TEXT,
                "completeness_state": COMP_COMPLETE, "reason": None, "byte_count": len(raw),
                "_live_size": len(raw)}

    def _complete_parser(self, abs_path: Path, ext: str, max_bytes: int | None) -> dict[str, Any]:
        from hb_assistant.files.parsers.isolated import (
            STATUS_FAILED,
            STATUS_OK,
            STATUS_OUTPUT_TOO_LARGE,
            STATUS_RESOURCE_EXCEEDED,
            STATUS_TIMEOUT,
            STATUS_TOO_LARGE,
            STATUS_UNSUPPORTED,
            extract_for_complete_read,
        )

        res = extract_for_complete_read(
            abs_path, ext,
            max_input_bytes=int(self._config.source_complete_read_max_input_bytes),
            max_output_bytes=self._effective_output_limit(max_bytes),
            timeout_s=float(self._config.source_parser_isolation_timeout_seconds),
            max_memory_mb=int(self._config.source_parser_max_memory_mb),
        )
        if res.status == STATUS_OK:
            return {"content": res.text, "char_count": res.char_count,
                    "content_source": CONTENT_LIVE_EXTRACT, "truncated": False,
                    "retrieval_state": RS_COMPLETE, "content_state": CS_EXTRACTED,
                    "completeness_state": COMP_COMPLETE, "reason": None, "byte_count": res.output_bytes}
        state_map = {
            STATUS_TOO_LARGE: RS_TOO_LARGE,
            STATUS_OUTPUT_TOO_LARGE: RS_PARSER_OUTPUT_TOO_LARGE,
            STATUS_TIMEOUT: RS_PARSER_TIMEOUT,
            STATUS_FAILED: RS_PARSER_FAILED,
            STATUS_RESOURCE_EXCEEDED: RS_PARSER_RESOURCE_EXCEEDED,
            STATUS_UNSUPPORTED: RS_UNSUPPORTED,
        }
        retrieval_state = state_map.get(res.status, RS_PARSER_FAILED)
        out: dict[str, Any] = {
            "content": None, "char_count": 0, "content_source": None, "truncated": False,
            "retrieval_state": retrieval_state, "content_state": CS_NONE,
            "completeness_state": COMP_NONE, "reason": res.failure_code or res.status,
        }
        if res.observed_output_bytes_lower_bound is not None:
            out["output_bytes_lower_bound"] = res.observed_output_bytes_lower_bound
            out["recommended_next_action"] = "Content exceeds the complete-read budget; use mode='excerpt'."
        return out

    # ------------------------------------------------------------------ rename lineage (B4)

    def _resolve_moved(self, old_source_id: str, detail: dict[str, Any], mode: str,
                       conn: Any) -> dict[str, Any] | None:
        """Answer a deleted source_ref as ``moved`` iff an authorized, current successor exists. Returns
        None to fall through to ordinary deleted/unavailable handling."""
        new_sid = self._repo.find_successor_source_id(old_source_id, conn=conn)
        if not new_sid:
            return None
        succ = self._repo.get_source_detail(new_sid, conn=conn)
        if succ is None or succ.get("deleted"):
            return None  # lineage points to a missing/non-current successor -> no fabricated move
        succ_root = self._root_for(succ.get("source_root_key"))
        if succ_root is None or succ_root.sensitive:
            return None  # successor not authorized for disclosure -> ordinary unavailable
        prov = self._provenance(
            detail, old_source_id, retrieval_state=RS_MOVED, content_state=CS_METADATA_ONLY,
            completeness_state=COMP_NONE,
        )
        return {
            **self._base(detail, old_source_id),
            "mode": mode,
            "content": None,
            "char_count": 0,
            "content_source": None,
            "truncated": False,
            "retrieval_state": RS_MOVED,
            "content_state": CS_METADATA_ONLY,
            "completeness_state": COMP_NONE,
            "denied": False,
            "reason": "renamed",
            "successor_source_ref": encode_source_ref(new_sid),
            "successor_source_id": new_sid,
            "provenance": prov,
        }

    # ------------------------------------------------------------------ dispatch

    def read(self, source_id: str, *, max_chars: int | None = None, max_bytes: int | None = None,
             prefer_live: bool = True, mode: str = READ_MODE_EXCERPT,
             conn: Any = None) -> dict[str, Any]:
        """Read one source. ``mode='excerpt'`` (default) returns a bounded excerpt; ``mode='complete'``
        returns a complete-or-explicit-failure read. Raises only when the source_id is unknown or the
        mode is invalid."""
        if mode not in (READ_MODE_EXCERPT, READ_MODE_COMPLETE):
            raise SourceConnectorValidationError("invalid_request")
        detail = self._repo.get_source_detail(source_id, conn=conn)
        if detail is None:
            raise SourceConnectorValidationError("source_not_found")
        # B4 lineage-lookup ordering: an old (deleted) source_ref with an authorized successor answers
        # `moved` BEFORE the generic deleted -> unavailable branch. A missing/non-current/unauthorized
        # successor falls through to ordinary unavailable (never a fabricated move).
        if detail.get("deleted"):
            moved = self._resolve_moved(source_id, detail, mode, conn)
            if moved is not None:
                return moved
        if mode == READ_MODE_COMPLETE:
            return self._read_complete(source_id, detail, max_bytes=max_bytes, conn=conn)
        resp = self._read_excerpt(source_id, detail, max_chars=max_chars,
                                  prefer_live=prefer_live, conn=conn)
        return self._annotate_excerpt_states(resp, detail, source_id)
