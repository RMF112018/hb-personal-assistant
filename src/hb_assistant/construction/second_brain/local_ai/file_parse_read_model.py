"""Phase 10 — review-safe document/file parse read-model (local-only, raw-free).

Runs the repo's existing bounded local parsers (``hb_assistant.files.router.ParserRouter`` — pdf via
pdfplumber+pypdf, docx via python-docx, xlsx via openpyxl, pptx via python-pptx, csv/txt/md via the
stdlib, image metadata via Pillow) and projects the result into a **review-safe read-model that never
carries the extracted text**: only file id / sanitized name / extension / MIME / parsed status /
extraction method / text length + sha256 hash / page-table-sheet counts / degraded reason / source
refs / redaction flags. Local tooling only — no network, no upload, no model. Deterministic.
"""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import Any, Optional

# Extensions the bounded router supports, with the local extraction method for each.
_EXTRACTION_METHOD: dict[str, str] = {
    ".pdf": "pdfplumber+pypdf",
    ".docx": "python-docx",
    ".xlsx": "openpyxl",
    ".xlsm": "openpyxl",
    ".pptx": "python-pptx",
    ".csv": "stdlib-csv",
    ".txt": "stdlib-text",
    ".md": "stdlib-text",
    ".png": "pillow-metadata",
    ".jpg": "pillow-metadata",
    ".jpeg": "pillow-metadata",
    ".webp": "pillow-metadata",
    ".gif": "pillow-metadata",
    ".zip": "stdlib-zipfile",
}
_SUPPORTED = frozenset(_EXTRACTION_METHOD)
_COUNT_KEYS = ("page_count", "table_count", "sheet_count", "slide_count", "row_count")


def _source_id_for(name: str, explicit: Optional[str]) -> str:
    return explicit or "file:" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]


def build_file_parse_read_model(
    path: str | Path,
    *,
    source_id: Optional[str] = None,
    source_refs: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Parse one file with a local bounded parser → review-safe read-model (never the extracted text)."""
    p = Path(path)
    ext = p.suffix.lower()
    mime, _ = mimetypes.guess_type(p.name)
    base: dict[str, Any] = {
        "source_id": _source_id_for(p.name, source_id),
        "file_name": p.name,  # basename only — never a full path
        "extension": ext,
        "mime_type": mime,
        "source_refs": list(source_refs or []),
        "redaction": {
            "raw_text_excerpt_excluded": True,
            "hash_only": True,
            "local_only": True,
            "no_model": True,
        },
    }

    if not p.exists():
        return {**base, "parsed_status": "error", "extraction_method": None,
                "text_length": 0, "text_hash": None, "counts": {},
                "degraded_reason": "file_not_found"}
    if ext not in _SUPPORTED:
        return {**base, "parsed_status": "unsupported", "extraction_method": None,
                "text_length": 0, "text_hash": None, "counts": {},
                "degraded_reason": f"unsupported_extension:{ext or '(none)'}"}

    from hb_assistant.files.router import ParserRouter

    result = ParserRouter().parse(p)
    excerpt = str(result.get("text_excerpt") or "")
    text_length = int(result.get("char_count") or len(excerpt))
    text_hash = (
        "sha256:" + hashlib.sha256(excerpt.encode("utf-8", "replace")).hexdigest()
        if excerpt
        else None
    )
    failure_code = result.get("failure_code")
    err = result.get("error")
    status = "degraded" if (failure_code or err) else "parsed"
    return {
        **base,
        "parsed_status": status,
        "extraction_method": _EXTRACTION_METHOD.get(ext),
        "text_length": text_length,
        "text_hash": text_hash,
        "counts": {k: result[k] for k in _COUNT_KEYS if k in result},
        # Prefer the bounded failure code; an error string is bounded and carries no extracted text.
        "degraded_reason": failure_code or (str(err)[:120] if err else None),
    }


def build_file_index_read_model(
    paths: list[str | Path],
    *,
    source_refs_by_name: Optional[dict[str, list[str]]] = None,
) -> dict[str, Any]:
    """Build a review-safe file index read-model over many files (counts + per-file read-models)."""
    refs = source_refs_by_name or {}
    items = [
        build_file_parse_read_model(p, source_refs=refs.get(Path(p).name))
        for p in paths
    ]
    by_status: dict[str, int] = {}
    by_ext: dict[str, int] = {}
    for it in items:
        by_status[it["parsed_status"]] = by_status.get(it["parsed_status"], 0) + 1
        by_ext[it["extension"] or "(none)"] = by_ext.get(it["extension"] or "(none)", 0) + 1
    return {
        "command": "second-brain files parse-index",
        "ok": True,
        "counts": {"files": len(items), "by_status": by_status, "by_extension": by_ext},
        "files": items,
        "guardrails": {
            "local_only": True,
            "no_network": True,
            "no_model": True,
            "no_raw_text_excerpt": True,
            "hash_only": True,
            "no_writeback": True,
            "deterministic": True,
        },
    }


def render_file_index_markdown(index: dict[str, Any]) -> str:
    """Render the file parse index as legible, raw-free operator markdown."""
    if not index.get("ok"):
        return f"# File Parse Index\n\n_Unavailable: {index.get('error')}_\n"
    counts = index.get("counts", {})
    lines = [
        "# File Parse Index (review-safe read-model)",
        "",
        f"_files: {counts.get('files', 0)} · by status: {counts.get('by_status')} · "
        f"by extension: {counts.get('by_extension')} · local-only, hash-only, no model._",
        "",
        "## Files",
    ]
    for it in index.get("files", []):
        cnts = it.get("counts") or {}
        cnt_s = ", ".join(f"{k}={v}" for k, v in cnts.items()) or "—"
        lines.append(
            f"- **{it.get('file_name')}** ({it.get('extension')} · {it.get('mime_type') or 'n/a'}) "
            f"→ **{it.get('parsed_status')}** via {it.get('extraction_method') or '(none)'}"
        )
        lines.append(
            f"  - id: {it.get('source_id')} · text_length: {it.get('text_length')} · "
            f"hash: {it.get('text_hash') or '(none)'} · counts: {cnt_s}"
            + (f" · degraded: {it['degraded_reason']}" if it.get("degraded_reason") else "")
        )
    return "\n".join(lines) + "\n"
