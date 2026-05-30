"""Phase 06A — safe Obsidian projections for SharePoint / OneDrive file intelligence.

Local-only renderer over the V5 files SQLite tables (source locations, drive
items, project matches, ingestion decisions, crawl runs, download/extraction
receipts, and the sensitive-file review queue). Produces **grouped, low-noise**
markdown artifacts — never one note per file:

- Source Manifest (one per source): scope/site/drive ids, item counts, last
  sync, and a **delta-link fingerprint only** (never the raw delta token).
- Project File Register (one per project): counts by match status + ingestion
  disposition and a capped metadata table. No full text, no raw delta links.
- Review Summary (one per project): the sensitive files Prompt 12 routed into
  ``construction_review_queue``, grouped by category/sensitivity.
- Processing Receipt (one per run): crawl + download/extraction counts with
  no-full-text / no-vault-copy attestations; redacted errors only.

This mirrors :class:`EmailObsidianProjector` (its own grouped artifacts +
marker-bounded ``_write_artifact`` + output fence + dry-run-default), reusing
``delta_link_fingerprint``. It deliberately does **not** touch the V2
``ManifestService`` (a parallel construction-agent/email path). Read-only against
Microsoft 365: SQLite only — no Graph, no writeback, no source files or document
text copied into Obsidian. Dry-run is the default.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.manifests.service import delta_link_fingerprint
from hb_assistant.construction.store import ConstructionStore

_BASE = "Work/HB Personal Assistant/07_File_Intelligence"
_MARKER_PREFIX = "HB-FILES"
_TABLE_CAP = 50

# Output fence: a rendered note must never contain any of these. Plain SharePoint
# ``web_url`` item links are allowed (traceability) — we do NOT blanket-ban URLs;
# only signed-URL params, the Graph downloadUrl, auth material, raw delta tokens,
# PEM blocks, and full-text markers are forbidden.
_PEM_MARKER = "-----" + "begin"
_FORBIDDEN_MARKERS = (
    "deltatoken=",
    "?token=",
    "&token=",
    "sig=",
    "@microsoft.graph.downloadurl",
    "authorization:",
    "bearer ",
    "access_token",
    "refresh_token",
    "client_secret",
    _PEM_MARKER,
    "full_document_text",
    "full_body_" + "plaintext",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _assert_output_fence(rendered: str) -> None:
    lower = (rendered or "").lower()
    for tok in _FORBIDDEN_MARKERS:
        if tok in lower:
            raise ValueError(
                f"output-fence violation: forbidden marker {tok!r} in generated files Obsidian content"
            )


def _md_cell(value: Any) -> str:
    """Single-line, pipe-safe table cell."""
    text = " ".join(str(value if value is not None else "").split())
    return text.replace("|", "/")


class FileObsidianReport(BaseModel):
    source_id: Optional[str] = None
    project_key: Optional[str] = None
    dry_run: bool
    generated_at: str
    notes_planned: int
    notes_written: int
    sources_referenced: int
    files_referenced: int
    review_items_referenced: int
    paths: list[str]
    guardrails: dict[str, Any]

    model_config = {"extra": "forbid"}


@dataclass
class _FileArtifact:
    kind: str
    relative_path: str
    marker_key: str
    content: str


class FileObsidianProjector:
    """Build/write grouped files Obsidian artifacts from local SQLite state."""

    def __init__(self, store: ConstructionStore) -> None:
        self._store = store

    def project(
        self,
        *,
        source_id: Optional[str] = None,
        project_key: Optional[str] = None,
        dry_run: bool = True,
    ) -> FileObsidianReport:
        sources = self._resolve_sources(source_id=source_id, project_key=project_key)
        run_id = f"files-obsidian-{uuid.uuid4().hex[:12]}"

        files_referenced = 0
        review_items_referenced = 0
        artifacts: list[_FileArtifact] = []

        # Per-source manifests + accumulators for project-grouped registers/reviews.
        by_project: dict[str, list[dict[str, Any]]] = {}
        for src in sources:
            sid = src["source_id"]
            items = [
                it
                for it in self._store.list_drive_items(source_id=sid, limit=100000)
                if not it.get("deleted")
            ]
            files = [it for it in items if it.get("is_file")]
            files_referenced += len(files)
            matches = {
                m["drive_item_id"]: m
                for m in self._store.list_drive_item_project_matches(source_id=sid, limit=100000)
            }
            decisions = {
                d["drive_item_id"]: d
                for d in self._store.list_file_ingestion_decisions(source_id=sid, limit=100000)
            }
            sync = self._store.get_source_sync_state(sid) or {}
            crawl_runs = self._store.list_source_crawl_runs(source_id=sid, limit=50)
            dl = self._store.list_download_receipts(source_id=sid, limit=100000)
            ext = self._store.list_file_extraction_runs(source_id=sid, limit=100000)

            artifacts.append(
                _FileArtifact(
                    kind="source_manifest",
                    relative_path=f"{_BASE}/Source Manifests/{sid}.md",
                    marker_key="source_manifest",
                    content=self._render_source_manifest(
                        src=src, run_id=run_id, items=items, sync=sync
                    ),
                )
            )
            pkey = src.get("project_key") or "_unassigned_"
            by_project.setdefault(pkey, []).append(
                {
                    "src": src,
                    "files": files,
                    "matches": matches,
                    "decisions": decisions,
                    "crawl_runs": crawl_runs,
                    "dl": dl,
                    "ext": ext,
                }
            )

        # One register + one review summary per project.
        for pkey, bundles in sorted(by_project.items()):
            artifacts.append(
                _FileArtifact(
                    kind="file_register",
                    relative_path=f"{_BASE}/Projects/{pkey}/File Register.md",
                    marker_key="file_register",
                    content=self._render_register(project=pkey, run_id=run_id, bundles=bundles),
                )
            )
            review_rows: list[dict[str, Any]] = []
            for b in bundles:
                review_rows.extend(
                    self._store.list_review_queue(
                        source_key=b["src"]["source_id"], status="open", limit=100000
                    )
                )
            review_items_referenced += len(review_rows)
            artifacts.append(
                _FileArtifact(
                    kind="review_required",
                    relative_path=f"{_BASE}/Review/{pkey} File Review.md",
                    marker_key="review_required",
                    content=self._render_review(project=pkey, run_id=run_id, rows=review_rows),
                )
            )

        # One processing receipt for the run (aggregated across scoped sources).
        artifacts.append(
            _FileArtifact(
                kind="processing_receipt",
                relative_path=f"{_BASE}/Sync Receipts/File Processing Receipt.md",
                marker_key="processing_receipt",
                content=self._render_receipt(run_id=run_id, by_project=by_project),
            )
        )

        # Fence every rendered artifact at build time (so dry-run previews are safe too).
        for a in artifacts:
            _assert_output_fence(a.content)

        written = 0
        abs_paths: list[str] = []
        if dry_run:
            abs_paths = [str(self._abs_target_path(a.relative_path)) for a in artifacts]
        else:
            for a in artifacts:
                abs_paths.append(str(self._write_artifact(a)))
                written += 1

        return FileObsidianReport(
            source_id=source_id,
            project_key=project_key,
            dry_run=dry_run,
            generated_at=_utc_now(),
            notes_planned=len(artifacts),
            notes_written=written,
            sources_referenced=len(sources),
            files_referenced=files_referenced,
            review_items_referenced=review_items_referenced,
            paths=abs_paths,
            guardrails=self._guardrails(),
        )

    # --- scope ----------------------------------------------------------------

    def _resolve_sources(
        self, *, source_id: Optional[str], project_key: Optional[str]
    ) -> list[dict[str, Any]]:
        if source_id is not None:
            src = self._store.get_source_location(source_id)
            return [src] if src else []
        return self._store.list_source_locations(project_key=project_key, limit=100000)

    def _guardrails(self) -> dict[str, Any]:
        return {
            "external_systems": "read_only",
            "writeback": "none",
            "graph_calls": "none",
            "permission_tightening": "deferred",
            "source_traceability": True,
            "full_text_persisted": False,
            "source_file_copied_to_vault": False,
            "raw_delta_links_rendered": False,
            "one_note_per_file": False,
            "marker_bounded_writes": True,
        }

    # --- write ----------------------------------------------------------------

    def _abs_target_path(self, relative_path: str) -> Path:
        return PathPolicy().get_vault_root() / relative_path

    def _write_artifact(self, artifact: _FileArtifact) -> Path:
        target = self._abs_target_path(artifact.relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        start = f"<!-- {_MARKER_PREFIX}-{artifact.marker_key.upper()}:START -->"
        end = f"<!-- {_MARKER_PREFIX}-{artifact.marker_key.upper()}:END -->"
        if start not in existing or end not in existing:
            if existing and not existing.endswith("\n"):
                existing += "\n"
            existing = existing + f"\n{start}\n{end}\n"
        pattern = re.compile(rf"({re.escape(start)})(.*?)({re.escape(end)})", re.DOTALL)
        rendered = pattern.sub(rf"\1\n{artifact.content.strip()}\n\3", existing)
        _assert_output_fence(rendered)
        target.write_text(rendered, encoding="utf-8")
        return target

    # --- renderers ------------------------------------------------------------

    def _render_source_manifest(
        self, *, src: dict[str, Any], run_id: str, items: list[dict[str, Any]], sync: dict[str, Any]
    ) -> str:
        sid = src["source_id"]
        files = [it for it in items if it.get("is_file")]
        folders = [it for it in items if it.get("is_folder")]
        deleted = sum(
            1
            for it in self._store.list_drive_items(source_id=sid, limit=100000)
            if it.get("deleted")
        )
        fp = delta_link_fingerprint(sync.get("delta_link")) or sync.get("delta_link_fingerprint")
        lines = [
            "---",
            f"source_id: {sid}",
            f"project_key: {src.get('project_key') or ''}",
            f"run_id: {run_id}",
            f"generated_at: {_utc_now()}",
            "graph_operation_mode: dry_run",
            "writeback: none",
            "external_systems: read_only",
            "permission_tightening: deferred",
            "source_traceability: true",
            "---",
            "",
            f"# Source Manifest — {_md_cell(src.get('source_name') or sid)}",
            "",
            "## Summary",
            "",
            f"- Source scope: {_md_cell(src.get('source_scope'))}",
            f"- Source system: {_md_cell(src.get('source_system'))}",
            f"- Site ID: {_md_cell(src.get('site_id'))}",
            f"- Drive ID: {_md_cell(src.get('drive_id'))}",
            f"- Folder item ID: {_md_cell(src.get('folder_item_id'))}",
            f"- Library: {_md_cell(src.get('library_name'))}",
            f"- Items active: {len(items)}",
            f"- Files: {len(files)}",
            f"- Folders: {len(folders)}",
            f"- Items deleted: {deleted}",
            f"- Last sync: {_md_cell(sync.get('last_successful_sync_utc'))}",
            f"- Sync status: {_md_cell(sync.get('sync_status'))}",
            f"- Delta fingerprint: {_md_cell(fp)}",
            "",
            "## Guardrails",
            "",
            "- No Microsoft 365 writeback; read-only metadata projection.",
            "- No source files copied into Obsidian; no full document text stored.",
            "- Raw delta links never rendered (SHA-256 fingerprint only).",
            "- Broad Graph file permission tightening is deferred (documented risk).",
        ]
        return "\n".join(lines)

    def _render_register(self, *, project: str, run_id: str, bundles: list[dict[str, Any]]) -> str:
        rows: list[dict[str, Any]] = []
        by_status: dict[str, int] = {}
        by_disposition: dict[str, int] = {}
        for b in bundles:
            sid = b["src"]["source_id"]
            for it in b["files"]:
                iid = it["drive_item_id"]
                m = b["matches"].get(iid, {})
                d = b["decisions"].get(iid, {})
                status = m.get("match_status") or "unmatched"
                disp = d.get("ingestion_disposition") or "metadata_only"
                by_status[status] = by_status.get(status, 0) + 1
                by_disposition[disp] = by_disposition.get(disp, 0) + 1
                rows.append(
                    {
                        "name": it.get("name"),
                        "source": sid,
                        "parent": it.get("parent_reference_path") or it.get("path"),
                        "status": status,
                        "disposition": disp,
                        "extraction_allowed": bool(d.get("extraction_allowed")),
                        "review_required": bool(d.get("review_required"))
                        or bool(m.get("review_required"))
                        or disp == "review_required",
                    }
                )

        lines = [
            f"# Project File Register — {_md_cell(project)}",
            "",
            f"_Run {run_id} · generated {_utc_now()} · {len(rows)} files across "
            f"{len(bundles)} source(s)._",
            "",
            "## Counts by match status",
            "",
        ]
        lines += [f"- {_md_cell(k)}: {v}" for k, v in sorted(by_status.items())] or ["- (none)"]
        lines += ["", "## Counts by ingestion disposition", ""]
        lines += [f"- {_md_cell(k)}: {v}" for k, v in sorted(by_disposition.items())] or [
            "- (none)"
        ]
        lines += [
            "",
            f"## Files (showing up to {_TABLE_CAP} of {len(rows)})",
            "",
            "| Name | Source | Folder | Match | Disposition | Extract | Review |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for r in rows[:_TABLE_CAP]:
            lines.append(
                f"| {_md_cell(r['name'])} | {_md_cell(r['source'])} | {_md_cell(r['parent'])} "
                f"| {_md_cell(r['status'])} | {_md_cell(r['disposition'])} "
                f"| {'yes' if r['extraction_allowed'] else 'no'} "
                f"| {'yes' if r['review_required'] else 'no'} |"
            )
        if len(rows) > _TABLE_CAP:
            lines.append("")
            lines.append(f"_+{len(rows) - _TABLE_CAP} more not shown (SQLite is authoritative)._")
        lines += [
            "",
            "_Metadata only — no document text, no raw delta links, no source files copied._",
        ]
        return "\n".join(lines)

    def _render_review(self, *, project: str, run_id: str, rows: list[dict[str, Any]]) -> str:
        by_label: dict[str, int] = {}
        by_sensitivity: dict[str, int] = {}
        for r in rows:
            label = r.get("classification_label") or "unclassified"
            sens = r.get("sensitivity") or "unknown"
            by_label[label] = by_label.get(label, 0) + 1
            by_sensitivity[sens] = by_sensitivity.get(sens, 0) + 1

        lines = [
            f"# File Review Summary — {_md_cell(project)}",
            "",
            f"_Run {run_id} · generated {_utc_now()} · {len(rows)} open review item(s)._",
            "",
            "Sensitive / low-confidence files routed for controller review before any extraction.",
            "",
            "## By category",
            "",
        ]
        lines += [f"- {_md_cell(k)}: {v}" for k, v in sorted(by_label.items())] or ["- (none)"]
        lines += ["", "## By sensitivity", ""]
        lines += [f"- {_md_cell(k)}: {v}" for k, v in sorted(by_sensitivity.items())] or [
            "- (none)"
        ]
        lines += [
            "",
            f"## Items (showing up to {_TABLE_CAP} of {len(rows)})",
            "",
            "| Item | Source | Category | Sensitivity | Reason | Suggested action |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for r in rows[:_TABLE_CAP]:
            lines.append(
                f"| {_md_cell(r.get('name') or r.get('item_id'))} | {_md_cell(r.get('source_key'))} "
                f"| {_md_cell(r.get('classification_label'))} | {_md_cell(r.get('sensitivity'))} "
                f"| {_md_cell(r.get('reason'))} | {_md_cell(r.get('suggested_action'))} |"
            )
        lines += [
            "",
            "_Review-routed files cannot extract (enforced by the V18 ingestion CHECK)._",
        ]
        return "\n".join(lines)

    def _render_receipt(self, *, run_id: str, by_project: dict[str, list[dict[str, Any]]]) -> str:
        pages = items = 0
        crawl_count = 0
        delta_recorded = 0
        dl_attempted = dl_completed = cache_deleted = 0
        ext_runs = full_text = vault_copies = 0
        errors: list[str] = []
        for bundles in by_project.values():
            for b in bundles:
                for c in b["crawl_runs"]:
                    crawl_count += 1
                    pages += int(c.get("pages_seen") or 0)
                    items += int(c.get("items_seen") or 0)
                    if c.get("delta_link_recorded"):
                        delta_recorded += 1
                    if c.get("error_redacted"):
                        errors.append(
                            f"{b['src']['source_id']}: {_md_cell(c.get('error_redacted'))}"
                        )
                for r in b["dl"]:
                    dl_attempted += 1 if r.get("download_attempted") else 0
                    dl_completed += 1 if r.get("download_completed") else 0
                    cache_deleted += 1 if r.get("cache_deleted_after_parse") else 0
                    if r.get("source_file_copied_to_vault"):
                        vault_copies += 1
                for r in b["ext"]:
                    ext_runs += 1
                    if r.get("full_text_persisted"):
                        full_text += 1

        lines = [
            "# File Processing Receipt",
            "",
            f"_Run {run_id} · generated {_utc_now()}._",
            "",
            "## Sync (crawl/delta)",
            "",
            f"- Crawl runs: {crawl_count}",
            f"- Pages seen: {pages}",
            f"- Items seen: {items}",
            f"- Delta links recorded: {delta_recorded}",
            "",
            "## Controlled download / extraction",
            "",
            f"- Download attempts: {dl_attempted}",
            f"- Downloads completed: {dl_completed}",
            f"- Caches deleted after parse: {cache_deleted}",
            f"- Extraction runs: {ext_runs}",
            "",
            "## Attestations",
            "",
            f"- Full document text persisted: {'true' if full_text else 'false'}",
            f"- Source files copied to vault: {'true' if vault_copies else 'false'}",
            "- Signed download URLs cached: false",
            "- Raw delta links rendered: false",
            "",
            "## Errors (redacted)",
            "",
        ]
        lines += [f"- {e}" for e in errors[:_TABLE_CAP]] or ["- (none)"]
        return "\n".join(lines)
