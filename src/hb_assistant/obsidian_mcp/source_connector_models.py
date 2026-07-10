"""Neutral, deterministic value layer for the N8C-12 NAS source-root connector.

No DB, no filesystem, no model, no LLM. This module owns:

* the **opaque source reference** codec — ``source_ref`` wraps the already-opaque 32-hex ``source_id``
  (itself a sha256 over ``kind|file|root|rel_path``), so a ref NEVER carries a rel_path, root key,
  filename, or absolute path in reversible plaintext. It is resolved to a ``source_id`` server-side only.
* the **deterministic keyset cursor** codec — an opaque token bound to a ``query_digest`` over
  (query, filters, order). Continuation is keyset over a stable composite sort tuple; a cursor whose digest
  or order does not match the current request is rejected (``cursor_query_mismatch``). Never offset-based.
* bounded row shaping that ALWAYS surfaces ``source_root_key`` + root-relative ``rel_path`` and NEVER an
  absolute host path, plus a static extension→mime map.

The connector is read-only: nothing here scans, opens, walks, or mutates anything.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from .memory_models import bound_text, sha256_hex

# Split versions (V120): the source-REFERENCE checksum version and the pagination-CURSOR version are
# distinct so ranking/candidate changes invalidate outstanding cursors WITHOUT invalidating stored source
# references. SOURCE_REF_VERSION keeps its original string so existing refs remain valid; only
# SOURCE_CURSOR_VERSION advances (weighted BM25 + metadata-only path candidates changed the ordering).
SOURCE_REF_VERSION = "source-connector-v1"
SOURCE_CURSOR_VERSION = "source-cursor-v2"
# Back-compat alias (refs): older imports of SOURCE_CONNECTOR_VERSION resolve to the ref version.
SOURCE_CONNECTOR_VERSION = SOURCE_REF_VERSION

# Caps (bounded reads/lists; the repo also clamps).
MAX_LIMIT = 100
DEFAULT_LIMIT = 25
MAX_SNIPPET_CHARS = 240
READ_MAX_CHARS = 20_000
READ_DEFAULT_CHARS = 4_000

# Stable list/search order and its result-shape label.
ORDER_ROOT_PATH = "source_root_key,rel_path,source_id"
ORDER_RANK_PATH = "rank,source_root_key,rel_path,source_id"

# Content-source labels for bounded reads.
CONTENT_LIVE_EXTRACT = "live_extract"
CONTENT_INDEXED_FALLBACK = "indexed_excerpt_fallback"

_SOURCE_REF_PREFIX = "hbsrc1_"

# Static, conservative extension→mime map (advisory only; never trusted for gating).
MIME_BY_EXT = {
    "md": "text/markdown",
    "markdown": "text/markdown",
    "txt": "text/plain",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "eml": "message/rfc822",
    "csv": "text/csv",
    "json": "application/json",
}


class SourceConnectorValidationError(ValueError):
    """Raised for a malformed/forged source_ref, a cursor/query mismatch, or a bad enum/bound."""


def canonical_json(obj: Any) -> str:
    """Stable JSON for digest/cursor inputs (sorted keys, compact separators)."""
    return json.dumps(obj or {}, sort_keys=True, separators=(",", ":"))


def mime_for_ext(ext: str | None) -> str | None:
    if not ext:
        return None
    return MIME_BY_EXT.get(str(ext).strip().lower().lstrip("."))


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64u_decode(token: str) -> bytes:
    pad = "=" * (-len(token) % 4)
    return base64.urlsafe_b64decode(token + pad)


def _source_id_checksum(source_id: str) -> str:
    """Version-bound short checksum so a forged/typo'd ref is rejected before any DB hit."""
    return sha256_hex(f"{SOURCE_REF_VERSION}|source_ref|{source_id}")[:8]


def encode_source_ref(source_id: str) -> str:
    """Opaque, path-free reference around the 32-hex ``source_id`` (id + version-bound checksum).

    The ref reveals nothing about the file location: ``source_id`` is a sha256, not a path.
    """
    sid = str(source_id or "")
    if len(sid) != 32 or any(ch not in "0123456789abcdef" for ch in sid):
        raise SourceConnectorValidationError("invalid_source_id")
    payload = f"{sid}{_source_id_checksum(sid)}"
    return _SOURCE_REF_PREFIX + _b64u_encode(payload.encode("ascii"))


def decode_source_ref(source_ref: str) -> str:
    """Resolve an opaque ``source_ref`` back to its ``source_id`` (server-side only). Validates the
    prefix + version-bound checksum; raises on any tampering. Does NOT confirm the source exists —
    the caller resolves it against the index."""
    ref = str(source_ref or "")
    if not ref.startswith(_SOURCE_REF_PREFIX):
        raise SourceConnectorValidationError("invalid_source_ref")
    try:
        decoded = _b64u_decode(ref[len(_SOURCE_REF_PREFIX):]).decode("ascii")
    except (ValueError, UnicodeDecodeError) as exc:
        raise SourceConnectorValidationError("invalid_source_ref") from exc
    if len(decoded) != 40:  # 32-hex id + 8-hex checksum
        raise SourceConnectorValidationError("invalid_source_ref")
    sid, checksum = decoded[:32], decoded[32:]
    if checksum != _source_id_checksum(sid):
        raise SourceConnectorValidationError("invalid_source_ref")
    return sid


def resolve_source_id(*, source_id: str | None = None, source_ref: str | None = None) -> str:
    """Accept either a raw ``source_id`` or an opaque ``source_ref``; return the ``source_id``."""
    if source_ref:
        return decode_source_ref(source_ref)
    sid = str(source_id or "")
    if len(sid) != 32 or any(ch not in "0123456789abcdef" for ch in sid):
        raise SourceConnectorValidationError("source_id_or_ref_required")
    return sid


def sanitize_fts_query(query: str) -> str:
    """Turn a user query into a safe FTS5 MATCH string by phrase-quoting each whitespace token.

    A raw token like ``23-435-01`` fed straight into ``MATCH`` is parsed as FTS5 query syntax (the
    hyphen/column grammar), yielding ``no such column: 435``. Wrapping each token in double quotes makes
    FTS5 treat it as a literal phrase, so hyphenated/dotted/coloned project numbers and ordinary words
    all match literally; multiple tokens keep implicit-AND semantics (``"foo" "bar"``). Embedded quotes
    are escaped by doubling. Returns ``""`` when the query has no usable tokens (caller should then skip
    the search rather than run an empty/invalid MATCH).
    """
    tokens = str(query or "").split()
    return " ".join('"' + tok.replace('"', '""') + '"' for tok in tokens if tok)


def clamp_limit(limit: int | None, *, default: int = DEFAULT_LIMIT, maximum: int = MAX_LIMIT) -> int:
    try:
        value = int(limit) if limit is not None else default
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, maximum))


def compute_query_digest(params: dict[str, Any]) -> str:
    """Digest binding a cursor to the exact (query, filters, order) it was issued for."""
    return sha256_hex(f"{SOURCE_CURSOR_VERSION}|{canonical_json(params)}")[:16]


def encode_cursor(*, query_digest: str, order: str, after: list[Any]) -> str:
    """Opaque keyset cursor. ``after`` is the stable sort tuple of the last returned row.

    For search the tuple leads with the bm25 ``rank`` float, which round-trips exactly through JSON
    (Python's shortest-repr float serialization), so keyset continuation is deterministic.
    """
    payload = {"v": SOURCE_CURSOR_VERSION, "qd": query_digest, "order": order, "after": after}
    return _b64u_encode(canonical_json(payload).encode("utf-8"))


def decode_cursor(cursor: str, *, query_digest: str, order: str) -> list[Any]:
    """Decode + validate a keyset cursor against the current request; return the ``after`` tuple.

    Rejects a cursor whose bound query digest or order differs from the current request
    (``cursor_query_mismatch``) so a client can never page across a changed query/filter/order.
    """
    try:
        payload = json.loads(_b64u_decode(str(cursor or "")).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise SourceConnectorValidationError("invalid_cursor") from exc
    if not isinstance(payload, dict) or payload.get("v") != SOURCE_CURSOR_VERSION:
        raise SourceConnectorValidationError("invalid_cursor")
    if payload.get("qd") != query_digest or payload.get("order") != order:
        raise SourceConnectorValidationError("cursor_query_mismatch")
    after = payload.get("after")
    if not isinstance(after, list):
        raise SourceConnectorValidationError("invalid_cursor")
    return after


def page_envelope(items: list[dict[str, Any]], *, limit: int, order: str, query_digest: str,
                  next_after: list[Any] | None, cursor: str | None) -> dict[str, Any]:
    """Deterministic cursor-window envelope shared by search + list.

    ``has_more`` / ``next_cursor`` are derived from a limit+1 fetch by the caller: when a next row
    exists, ``next_after`` is its sort tuple and a ``next_cursor`` is minted; otherwise both are null and
    ``truncated`` stays false (no silent truncation).
    """
    has_more = next_after is not None
    next_cursor = (
        encode_cursor(query_digest=query_digest, order=order, after=next_after) if has_more else None
    )
    return {
        "items": items,
        "count": len(items),
        "limit": limit,
        "limit_applied": True,
        "order": order,
        "has_more": has_more,
        "next_cursor": next_cursor,
        "cursor": cursor,
        "truncated": has_more,
    }


def bound_snippet(text: str | None) -> str | None:
    if text is None:
        return None
    return bound_text(str(text), MAX_SNIPPET_CHARS)


def shape_source_file(row: dict[str, Any], *, snippet: str | None = None,
                      include_snippet: bool = False) -> dict[str, Any]:
    """Bounded, root-aware search/list row. ALWAYS carries source_root_key + root-relative rel_path +
    an opaque source_ref; NEVER an absolute host path or raw body."""
    source_id = str(row["source_id"])
    ext = row.get("file_ext") or row.get("extension")
    shaped: dict[str, Any] = {
        "source_id": source_id,
        "source_ref": encode_source_ref(source_id),
        "source_root_key": row.get("source_root_key"),
        "rel_path": row.get("rel_path"),
        "source_kind": row.get("source_kind", "external_file"),
        "extension": (str(ext).lower().lstrip(".") if ext else None),
        "mime_type": mime_for_ext(ext),
    }
    if include_snippet:
        shaped["snippet"] = bound_snippet(snippet)
    return shaped
