"""Bounded, idempotent source indexing — runs OUTSIDE the MCP request path.

Deterministic extraction (reusing files/parsers/*), bounded excerpt/chunk caps, path→project
matching, and explicit writes via SourceIndexRepository. Never copies files into the vault.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hb_assistant.construction.email.project_matcher import HB_PROJECT_NUMBER_RE

from . import pathsafe
from .config import ExternalSourceRoot, ObsidianMcpConfig
from .source_index_repository import SourceIndexRepository

_logger = logging.getLogger("hb_assistant.obsidian_mcp.source_index")

_TEXT_EXTS = {"md", "markdown", "txt"}
_PARSER_EXTS = {"pdf", "docx", "xlsx"}
_TEMP_SUFFIXES = (".tmp", ".swp", ".swo", ".part", ".crdownload")
_TEMP_NAMES = {".ds_store"}


def should_ignore(rel_path: str, name: str) -> bool:
    """Skip protected/hidden/temp files (shared by scan + watcher)."""
    if pathsafe.path_blocked(rel_path, include_hidden=False):
        return True
    lower = name.lower()
    return lower in _TEMP_NAMES or lower.startswith("~$") or lower.endswith(_TEMP_SUFFIXES)


def match_path_to_project(rel_path: str) -> tuple[str | None, str | None, str]:
    """Deterministic HB project-number extraction from a path. Returns (key, number, confidence).

    Foundation slice: project_number comes from the NN-NNN-NN token; canonical project_key
    resolution against the registry is deferred to a later slice (key left None unless a single
    unambiguous number is present, in which case the number doubles as a filterable key).
    """
    numbers = sorted(set(HB_PROJECT_NUMBER_RE.findall(rel_path)))
    if len(numbers) == 1:
        return (numbers[0], numbers[0], "high")
    if len(numbers) > 1:
        return (None, numbers[0], "low")
    return (None, None, "none")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _extract(path: Path, ext: str, max_chars: int) -> dict[str, Any]:
    """Deterministic, best-effort extraction. Never raises on bad input."""
    if ext in _TEXT_EXTS:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:max_chars]
            return {"text_excerpt": text, "char_count": len(text), "extraction_status": "ok"}
        except OSError as exc:  # unreadable
            return {"text_excerpt": "", "char_count": 0, "extraction_status": "failed",
                    "failure_code": type(exc).__name__}
    try:
        if ext == "pdf":
            from hb_assistant.files.parsers.pdf import PDFParser
            r = PDFParser().parse(path, max_chars)
        elif ext == "docx":
            from hb_assistant.files.parsers.docx import DOCXParser
            r = DOCXParser().parse(path, max_chars)
        elif ext == "xlsx":
            from hb_assistant.files.parsers.xlsx import XLSXParser
            r = XLSXParser().parse(path, max_chars)
        else:
            return {"text_excerpt": None, "char_count": 0, "extraction_status": "unsupported"}
    except Exception as exc:  # parser robustness backstop
        return {"text_excerpt": "", "char_count": 0, "extraction_status": "failed",
                "failure_code": type(exc).__name__}
    status = "failed" if r.get("failure_code") else "ok"
    return {**r, "extraction_status": status}


def _chunks(text: str, max_chunks: int, max_chunk_chars: int) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    for i in range(0, len(text), max_chunk_chars):
        out.append(text[i : i + max_chunk_chars])
        if len(out) >= max_chunks:
            break
    return out


def index_source_file(abs_path: Path, root: ExternalSourceRoot, repo: SourceIndexRepository,
                      config: ObsidianMcpConfig, *, conn: Any = None) -> str | None:
    """Index one external file (idempotent caller decides skip). Returns source_id or None."""
    root_path = Path(root.path)
    try:
        rel_path = str(abs_path.relative_to(root_path))
    except ValueError:
        return None
    ext = abs_path.suffix.lower().lstrip(".")
    try:
        stat = abs_path.stat()
    except OSError:
        return None
    size = stat.st_size
    max_excerpt = int(getattr(config, "source_index_max_excerpt_chars", 8000))

    record: dict[str, Any] = {
        "source_kind": "external_file", "source_root_key": root.source_root_key,
        "rel_path": rel_path, "abs_path_hash": hashlib.sha256(str(abs_path).encode()).hexdigest()[:32],
        "file_ext": ext, "size_bytes": size, "mtime_ns": stat.st_mtime_ns,
    }
    key, number, conf = match_path_to_project(rel_path)
    record["project_key"], record["project_number"] = key, number
    if number:
        record["relationships"] = [{
            "dst_kind": "project", "dst_ref": number, "relation": "belongs_to_project", "confidence": conf,
        }]

    record["content_sha256"] = _sha256_file(abs_path)
    if size > int(getattr(config, "max_file_mb", 100)) * 1024 * 1024:
        record["extraction_status"] = "skipped_too_large"
    else:
        ex = _extract(abs_path, ext, max_excerpt)
        record["extraction_status"] = ex.get("extraction_status", "ok")
        record["extraction_failure_code"] = ex.get("failure_code")
        record["page_count"] = ex.get("page_count")
        record["paragraph_count"] = ex.get("paragraph_count")
        record["sheet_count"] = ex.get("sheet_count")
        excerpt = ex.get("text_excerpt")
        if excerpt:
            if root.sensitive:
                # Sensitive root: encrypt the excerpt to the Text Vault; keep only a marker in-DB,
                # and DO NOT index sensitive text into FTS.
                from hb_assistant.security.text_vault import encrypt_text
                record["text_vault_ref"] = encrypt_text(excerpt)
                record["text_excerpt"] = None
                record["excerpt_char_count"] = 0
            else:
                record["text_excerpt"] = excerpt[:max_excerpt]
                record["excerpt_char_count"] = len(record["text_excerpt"])
                record["excerpt_truncated"] = len(excerpt) >= max_excerpt
                record["full_text_sha256"] = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
                record["chunks"] = _chunks(
                    excerpt,
                    int(getattr(config, "source_index_max_chunks", 40)),
                    int(getattr(config, "source_index_max_chunk_chars", 1500)),
                )
    return repo.upsert_source_file(record, conn=conn)


_VAULT_ROOT_KEY = "__vault_notes__"
_TAG_RE = __import__("re").compile(r"(?:^|\s)#([A-Za-z0-9_/\-]+)")


def _note_tags(text: str) -> str:
    """Space-joined tag set from inline #tags + a simple frontmatter ``tags:`` line."""
    tags = set(_TAG_RE.findall(text))
    head = text[:2000]
    if head.startswith("---"):
        for line in head.splitlines():
            stripped = line.strip()
            if stripped.startswith("tags:"):
                rest = stripped[len("tags:"):].strip().strip("[]")
                tags.update(t.strip().strip("'\"#") for t in rest.replace(",", " ").split() if t.strip())
    return " ".join(sorted(t for t in tags if t))


def index_obsidian_note(abs_path: Path, vault_root: Path, repo: SourceIndexRepository,
                        config: ObsidianMcpConfig, *, conn: Any = None) -> str | None:
    try:
        rel_path = str(abs_path.relative_to(vault_root))
        stat = abs_path.stat()
        text = abs_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return None
    max_excerpt = int(getattr(config, "source_index_max_excerpt_chars", 8000))
    excerpt = text[:max_excerpt]
    _, number, _conf = match_path_to_project(rel_path)
    record: dict[str, Any] = {
        "source_kind": "obsidian_note", "source_root_key": _VAULT_ROOT_KEY, "rel_path": rel_path,
        "file_ext": "md", "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns,
        "content_sha256": _sha256_file(abs_path), "extraction_status": "ok",
        "text_excerpt": excerpt, "excerpt_char_count": len(excerpt),
        "excerpt_truncated": len(text) > max_excerpt,
        "full_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "project_number": number, "fts_aux": _note_tags(text),
    }
    return repo.upsert_source_file(record, conn=conn)


def scan_vault_notes(repo: SourceIndexRepository, config: ObsidianMcpConfig) -> "ScanReport":
    """Bounded, idempotent index of the Obsidian vault's markdown notes into the note FTS."""
    report = ScanReport(root_key=_VAULT_ROOT_KEY)
    vault_root = Path(config.vault_root)
    if not vault_root.is_dir():
        report.error_codes.append("vault_root_not_found")
        report.errors += 1
        return report
    max_files = int(getattr(config, "external_source_scan_max_files", 5000))
    seen: set[str] = set()
    for abs_path in sorted(vault_root.rglob("*.md")):
        if not abs_path.is_file():
            continue
        rel_path = str(abs_path.relative_to(vault_root))
        if should_ignore(rel_path, abs_path.name) or pathsafe.symlink_escapes(abs_path, vault_root):
            continue
        report.scanned += 1
        if report.scanned > max_files:
            report.truncated = True
            break
        seen.add(rel_path)
        try:
            existing = repo.lookup_by_path("obsidian_note", rel_path)
            if (existing and not existing["deleted"]
                    and existing["mtime_ns"] == abs_path.stat().st_mtime_ns
                    and existing["content_sha256"] == _sha256_file(abs_path)):
                report.skipped += 1
                continue
            if index_obsidian_note(abs_path, vault_root, repo, config) is not None:
                report.indexed += 1
        except Exception as exc:
            report.errors += 1
            report.error_codes.append(type(exc).__name__)
    for gone in repo.active_rel_paths(_VAULT_ROOT_KEY) - seen:
        repo.mark_deleted("obsidian_note", gone)
        report.deleted += 1
    return report


@dataclass
class ScanReport:
    root_key: str
    scanned: int = 0
    indexed: int = 0
    skipped: int = 0
    deleted: int = 0
    errors: int = 0
    truncated: bool = False
    error_codes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "root_key": self.root_key, "scanned": self.scanned, "indexed": self.indexed,
            "skipped": self.skipped, "deleted": self.deleted, "errors": self.errors,
            "truncated": self.truncated,
        }


def scan_source_root(root: ExternalSourceRoot, repo: SourceIndexRepository,
                     config: ObsidianMcpConfig) -> ScanReport:
    """Bounded, idempotent walk of one root. NEVER called from a request handler."""
    report = ScanReport(root_key=root.source_root_key)
    root_path = Path(root.path)
    if not root_path.is_dir():
        report.error_codes.append("root_not_found")
        report.errors += 1
        return report

    max_files = int(getattr(config, "external_source_scan_max_files", 5000))
    seen: set[str] = set()
    for abs_path in sorted(root_path.rglob("*")):
        if not abs_path.is_file():
            continue
        try:
            rel_path = str(abs_path.relative_to(root_path))
        except ValueError:
            continue
        if should_ignore(rel_path, abs_path.name):
            continue
        if pathsafe.symlink_escapes(abs_path, root_path):
            continue
        report.scanned += 1
        if report.scanned > max_files:
            report.truncated = True
            break
        seen.add(rel_path)
        try:
            existing = repo.lookup_by_path("external_file", rel_path)
            if existing and not existing["deleted"]:
                stat = abs_path.stat()
                if existing["mtime_ns"] == stat.st_mtime_ns and existing["content_sha256"] == _sha256_file(abs_path):
                    report.skipped += 1
                    continue
            source_id = index_source_file(abs_path, root, repo, config)
            if source_id is not None:
                report.indexed += 1
                if existing:
                    repo.mark_generated_notes_stale(source_id)
        except Exception as exc:  # never let one bad file abort the scan
            report.errors += 1
            report.error_codes.append(type(exc).__name__)
            _logger.warning("source_index.scan_file_error", extra={"obsidian_mcp": {
                "root": root.source_root_key, "error_code": type(exc).__name__}})

    # Reconcile deletions: active indexed files under this root no longer on disk.
    for gone in repo.active_rel_paths(root.source_root_key) - seen:
        repo.mark_deleted("external_file", gone)
        report.deleted += 1
    return report


def _auto_generate(
    repo: SourceIndexRepository,
    config: ObsidianMcpConfig,
    source_id: str,
    root: ExternalSourceRoot,
    *,
    summaries_remaining: int,
) -> int:
    """Policy-driven card/summary generation after a successful index.

    Returns the number of advisory summaries produced (0 or 1) so the caller can enforce a
    per-drain cap. NEVER raises — an auto-gen failure must not fail the index event (indexing
    already succeeded). Sensitive roots get a card (preview withheld by the renderer) but never
    an advisory summary. Vault writes go through the existing write-policy in ``source_notes``.
    """
    from . import source_notes  # lazy import to avoid a module cycle

    detail = repo.get_source_detail(source_id)
    if detail is None or detail.get("deleted") or detail["source_kind"] == "obsidian_note":
        return 0
    kind = detail["source_kind"]

    want_card = (
        getattr(config, "source_card_auto_generate_enabled", False)
        and kind in getattr(config, "source_card_auto_generate_kinds", [])
        and getattr(config, "source_card_generation_enabled", True)
    )
    want_refresh = getattr(config, "source_note_auto_refresh_enabled", True)
    if want_card or (want_refresh and repo.has_generated_note(source_id)):
        with suppress(Exception):
            source_notes.generate_source_card(
                repo, config, source_id=source_id, overwrite=True, principal_kind="local"
            )

    want_summary = (
        summaries_remaining > 0
        and getattr(config, "source_summary_auto_generate_enabled", False)
        and getattr(config, "source_summary_enabled", True)
        and kind in getattr(config, "source_summary_auto_generate_kinds", [])
        and not getattr(root, "sensitive", False)
    )
    if want_summary:
        try:
            out = source_notes.summarize_source(repo, config, source_id=source_id, principal_kind="local")
        except Exception:  # noqa: BLE001 - advisory summary is best-effort
            return 0
        if out.get("summarized"):
            return 1
    return 0


def drain_queue(repo: SourceIndexRepository, config: ObsidianMcpConfig, *, batch: int = 50) -> int:
    """Process queued events (called by the watcher worker / rebuild path). Returns processed count."""
    roots = {r.source_root_key: r for r in config.external_sources}
    summary_cap = int(getattr(config, "source_summary_auto_max_per_drain", 5))
    summaries_done = 0
    processed = 0
    for event in repo.claim_queued(batch):
        try:
            if event["event_type"] == "rebuild":
                if event["source_root_key"] == _VAULT_ROOT_KEY:
                    scan_vault_notes(repo, config)
                else:
                    root = roots.get(event["source_root_key"])
                    if root and root.enabled:
                        scan_source_root(root, repo, config)
                repo.complete_event(event["event_id"], "done")
            elif event["event_type"] == "deleted":
                if event["rel_path"]:
                    repo.mark_deleted("external_file", event["rel_path"])
                repo.complete_event(event["event_id"], "done")
            else:  # created / modified / reindex_requested
                root = roots.get(event["source_root_key"])
                if root and event["rel_path"]:
                    source_id = index_source_file(Path(root.path) / event["rel_path"], root, repo, config)
                    if source_id is not None:
                        summaries_done += _auto_generate(
                            repo, config, source_id, root,
                            summaries_remaining=summary_cap - summaries_done,
                        )
                repo.complete_event(event["event_id"], "done")
            processed += 1
        except Exception as exc:
            repo.complete_event(event["event_id"], "error", error_code=type(exc).__name__)
    with suppress(Exception):
        repo.record_drain()
    return processed


def request_rebuild(repo: SourceIndexRepository, config: ObsidianMcpConfig) -> dict[str, Any]:
    """Enqueue a bounded rebuild per enabled root. NEVER scans inside the request."""
    enabled = [r for r in config.external_sources if r.enabled]
    if not getattr(config, "external_source_index_enabled", True):
        return {"accepted": False, "reason": "index_disabled", "roots_queued": 0}
    for root in enabled:
        repo.enqueue_event(event_type="rebuild", source_root_key=root.source_root_key)
    # Always (re)index the curated vault notes so broad search_vault is index-backed.
    repo.enqueue_event(event_type="rebuild", source_root_key=_VAULT_ROOT_KEY)

    # Drain off the request loop in a bounded one-shot thread, so an operator rebuild makes
    # progress even when the real-time watcher is OFF. claim_queued (queued->processing) makes
    # this safe to run alongside a live watcher worker without double-processing.
    def _drain() -> None:
        with suppress(Exception):
            while drain_queue(repo, config, batch=50) > 0:
                pass

    threading.Thread(target=_drain, name="source-rebuild-drain", daemon=True).start()
    return {"accepted": True, "roots_queued": len(enabled) + 1, "mode": "queued",
            "watch_enabled": bool(getattr(config, "external_source_watch_enabled", False))}
