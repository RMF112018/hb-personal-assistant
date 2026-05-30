"""Phase 06A — controlled, drive-aware file download + bounded redacted extraction.

The single place file *content* is fetched. Only items the V18 ingestion policy
marked ``extraction_allowed`` (disposition ``eligible``, not review-required) are
downloaded/extracted; everything else is skipped (``blocked_*``). Download and
extraction require explicit flags and are off in dry-run. Content streams to a
cache **outside the repo and vault** (`PathPolicy.get_cache_dir`), is hashed, parsed
into a **bounded redacted** excerpt, and the cache is deleted after parse unless
debug retention is requested. ``@microsoft.graph.downloadUrl`` is never used or
cached; full source text is never persisted; nothing is copied into Obsidian.

Reuses `GraphHttpClient.download_to_file` (drive-aware `/content` path), the files
`ParserRouter` + `ContentHasher`, the Prompt 02 endpoint guard, and the V18/V19
store tables. Read-only against Microsoft 365.
"""

from __future__ import annotations

import re
import uuid
from typing import Optional

from pydantic import BaseModel, Field

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.files.hasher import ContentHasher
from hb_assistant.files.router import ParserRouter
from hb_assistant.graph.files_endpoint_guard import assert_files_request_allowed
from hb_assistant.graph.http_client import GraphHttpClient, GraphHttpError

GRAPH_SCOPES = ["Files.ReadWrite.All", "User.Read"]
_DEFAULT_MAX_BYTES = 26214400  # 25 MiB
_EXCERPT_MAX_CHARS = 2000
PARSER_VERSION = "files-router-1"

# Token/PII-shaped patterns masked out of any persisted excerpt.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)")
_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_-]{24,}\b")


def _bounded_redact(text: Optional[str], max_chars: int = _EXCERPT_MAX_CHARS) -> str:
    """Cap to ``max_chars`` and mask emails / phones / long-token substrings.
    Never the full document — a bounded, scrubbed preview only."""
    if not text:
        return ""
    capped = text[:max_chars]
    capped = _EMAIL_RE.sub("[email-redacted]", capped)
    capped = _PHONE_RE.sub("[phone-redacted]", capped)
    capped = _TOKEN_RE.sub("[token-redacted]", capped)
    return capped


class ExtractionItemResult(BaseModel):
    source_id: str
    drive_item_id: str
    drive_id: Optional[str] = None
    name: Optional[str] = None
    project_key: Optional[str] = None
    disposition: str
    status: str  # would_download | would_extract | downloaded | extracted | blocked_<disp> | error | skipped
    downloaded: bool = False
    extracted: bool = False
    bytes_written: Optional[int] = None
    sha256: Optional[str] = None
    char_count: int = 0
    excerpt_preview: Optional[str] = None  # redacted, ≤120 chars; never full text
    cache_deleted: bool = False
    error_redacted: Optional[str] = None

    model_config = {"extra": "forbid"}


class ExtractionReport(BaseModel):
    command: str = "graph files extract"
    mode: str
    source: Optional[str] = None
    do_download: bool = False
    do_extract: bool = False
    summary: dict[str, int] = Field(default_factory=dict)
    items: list[ExtractionItemResult] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class ControlledExtractor:
    """Drive-aware controlled download + bounded extraction (offline-safe)."""

    def __init__(
        self,
        http_client: Optional[GraphHttpClient],
        store: ConstructionStore,
        *,
        parser: Optional[ParserRouter] = None,
        hasher: Optional[ContentHasher] = None,
        path_policy: Optional[PathPolicy] = None,
    ) -> None:
        self._http = http_client
        self._store = store
        self._parser = parser or ParserRouter()
        self._hasher = hasher or ContentHasher()
        self._pp = path_policy or PathPolicy()

    def run(
        self,
        source_id: str,
        *,
        dry_run: bool = True,
        do_download: bool = False,
        do_extract: bool = False,
        retain_cache: bool = False,
        max_bytes: int = _DEFAULT_MAX_BYTES,
    ) -> ExtractionReport:
        decisions = self._store.list_file_ingestion_decisions(source_id=source_id, limit=100000)
        # The decision row lacks file_extension; join it from the indexed drive items
        # so the cache filename keeps the source extension (parser dispatch).
        ext_by_id = {
            it["drive_item_id"]: (it.get("file_extension") or "")
            for it in self._store.list_drive_items(source_id=source_id, limit=100000)
        }
        results: list[ExtractionItemResult] = []
        for d in decisions:
            results.append(
                self._process(
                    d,
                    ext=ext_by_id.get(d["drive_item_id"], ""),
                    dry_run=dry_run,
                    do_download=do_download,
                    do_extract=do_extract,
                    retain_cache=retain_cache,
                    max_bytes=max_bytes,
                )
            )

        summary: dict[str, int] = {"total": len(results)}
        for r in results:
            summary[r.status] = summary.get(r.status, 0) + 1
        summary["downloaded"] = sum(1 for r in results if r.downloaded)
        summary["extracted"] = sum(1 for r in results if r.extracted)
        return ExtractionReport(
            mode="dry_run" if dry_run else "apply",
            source=source_id,
            do_download=do_download,
            do_extract=do_extract,
            summary=summary,
            items=results,
        )

    def _process(
        self,
        d: dict,
        *,
        ext: str,
        dry_run: bool,
        do_download: bool,
        do_extract: bool,
        retain_cache: bool,
        max_bytes: int,
    ) -> ExtractionItemResult:
        disp = d.get("ingestion_disposition") or "metadata_only"
        base = ExtractionItemResult(
            source_id=d["source_id"],
            drive_item_id=d["drive_item_id"],
            drive_id=d.get("drive_id"),
            project_key=d.get("project_key"),
            disposition=disp,
            status="skipped",
        )
        # Hard gate: only extraction_allowed (eligible, non-review) items proceed.
        if not d.get("extraction_allowed") or d.get("review_required"):
            base.status = f"blocked_{disp}" if disp != "eligible" else "blocked_review_required"
            return base

        if dry_run or not do_download:
            base.status = (
                "would_extract"
                if do_extract
                else "would_download"
                if do_download
                else "eligible_pending"
            )
            return base

        # Apply + --download: drive-aware controlled content fetch (guard-asserted).
        drive_id = d.get("drive_id")
        item_id = d["drive_item_id"]
        if not drive_id:
            base.status = "error"
            base.error_redacted = "missing_drive_id"
            return base
        path = f"/drives/{drive_id}/items/{item_id}/content"
        assert_files_request_allowed("GET", path)  # GET-only allowlisted; never downloadUrl
        # Cache filename keeps the source extension so the parser can dispatch.
        ext_clean = (ext or "bin").lstrip(".") or "bin"
        cache_dir = self._pp.get_cache_dir("files")
        cache_dir.mkdir(parents=True, exist_ok=True)
        target = cache_dir / f"{item_id}.{ext_clean}"

        if self._http is None:
            base.status = "error"
            base.error_redacted = "auth_required"
            return base

        try:
            written = self._http.download_to_file(
                path, target, max_bytes=max_bytes, scopes=GRAPH_SCOPES
            )
        except GraphHttpError as e:
            base.status = "error"
            base.error_redacted = f"graph_{e.status}"
            self._store.insert_download_receipt(
                receipt_id=str(uuid.uuid4()),
                source_id=base.source_id,
                drive_item_id=item_id,
                drive_id=drive_id,
                project_key=base.project_key,
                mode="apply",
                download_attempted=True,
                download_completed=False,
                status="error",
                error_redacted=base.error_redacted,
            )
            return base

        sha = self._hasher.hash_file(target)
        base.downloaded = True
        base.bytes_written = written
        base.sha256 = sha
        base.status = "downloaded"
        cache_deleted = False

        char_count = 0
        excerpt_redacted = ""
        if do_extract:
            parsed = self._parser.parse(target)
            excerpt_redacted = _bounded_redact(parsed.get("text_excerpt"))
            char_count = len(excerpt_redacted)
            self._store.insert_file_extraction_run(
                extraction_id=str(uuid.uuid4()),
                source_id=base.source_id,
                drive_item_id=item_id,
                drive_id=drive_id,
                project_key=base.project_key,
                parser_name="files-router",
                parser_version=PARSER_VERSION,
                content_hash=sha,
                extraction_status=("ok" if not parsed.get("error") else "parser_error"),
                text_excerpt_redacted=excerpt_redacted,
                char_count=char_count,
                review_required=False,
                error_redacted=(str(parsed.get("error"))[:150] if parsed.get("error") else None),
            )
            base.extracted = True
            base.char_count = char_count
            base.excerpt_preview = excerpt_redacted[:120]
            base.status = "extracted"

        # Delete cache after parse unless debug retention requested.
        if not retain_cache:
            try:
                target.unlink(missing_ok=True)
                cache_deleted = True
            except OSError:
                cache_deleted = False
        base.cache_deleted = cache_deleted

        self._store.insert_download_receipt(
            receipt_id=str(uuid.uuid4()),
            source_id=base.source_id,
            drive_item_id=item_id,
            drive_id=drive_id,
            project_key=base.project_key,
            mode="apply",
            download_attempted=True,
            download_completed=True,
            bytes_written=written,
            sha256=sha,
            cache_path_redacted=target.name,  # basename only — never an absolute path
            cache_deleted_after_parse=cache_deleted,
            status=base.status,
        )
        return base
