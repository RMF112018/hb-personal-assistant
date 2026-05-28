"""Deterministic Markdown rendering for construction-agent projections.

Templates live at ``resources/templates/*.template.md`` and use Python
``str.format`` substitution. The renderer is a pure function over Pydantic
models — same inputs → byte-identical output.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from hb_assistant.config.path_policy import PathPolicy

from .models import (
    DocumentCard,
    ProcessingReceipt,
    ProjectCard,
    RegistryOverview,
    ReviewRequiredNote,
    SourceManifest,
    SyncReceipt,
)

_TEMPLATE_NAMES = {
    "source_manifest": "source_manifest.template.md",
    "sync_receipt": "sync_receipt.template.md",
    "processing_receipt": "processing_receipt.template.md",
    "registry_overview": "registry_overview.template.md",
    "project_card": "project_card.template.md",
    "review_required": "review_required.template.md",
    "document_card": "document_card.template.md",
}


@lru_cache(maxsize=8)
def _load_template(name: str) -> str:
    repo_root = PathPolicy().resolve_repo_root()
    path = repo_root / "resources" / "templates" / _TEMPLATE_NAMES[name]
    return path.read_text(encoding="utf-8")


def _kv(value: object, missing: str = "n/a") -> str:
    if value is None or value == "":
        return missing
    return str(value)


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "_no items recorded_"
    return "\n".join(f"- {k}: {counts[k]}" for k in sorted(counts))


def _format_guardrails(guardrails: dict[str, str]) -> str:
    if not guardrails:
        return "_no guardrails recorded_"
    return "\n".join(f"- {k}: `{guardrails[k]}`" for k in sorted(guardrails))


def _format_sample_entries(entries: list, cap: int) -> str:
    if not entries:
        return "_no entries_"
    rows = ["| item_id | name | status | size_bytes | is_folder | last_modified |",
            "| --- | --- | --- | --- | --- | --- |"]
    for e in entries[:cap]:
        rows.append(
            f"| `{e.item_id}` | {_kv(e.name)} | `{e.status}` "
            f"| {_kv(e.size_bytes)} | {str(e.is_folder).lower()} "
            f"| {_kv(e.last_modified)} |"
        )
    return "\n".join(rows)


def _format_per_source(per_source: list[SyncReceipt]) -> str:
    if not per_source:
        return "_no sources processed_"
    rows = ["| source_key | mode | status | pages | items_seen | new | upd | del |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in per_source:
        rows.append(
            f"| `{r.source_key}` | `{r.mode}` | `{r.status}` "
            f"| {r.pages_seen} | {r.items_seen} "
            f"| {r.items_new} | {r.items_updated} | {r.items_deleted} |"
        )
    return "\n".join(rows)


def _format_error_block(error: str | None) -> str:
    if not error:
        return "_no errors_"
    return f"- `{error}`"


def _format_error_summary(errors: list[str]) -> str:
    if not errors:
        return "_no errors_"
    return "\n".join(f"- `{e}`" for e in errors)


def _format_projects_block(projects: list[dict]) -> str:
    if not projects:
        return "_no projects registered_"
    rows = ["| project_key | display_name | status | primary_company |",
            "| --- | --- | --- | --- |"]
    for p in projects:
        rows.append(
            f"| `{p.get('project_key', '')}` | {_kv(p.get('display_name'))} "
            f"| `{p.get('status', 'active')}` | {_kv(p.get('primary_company'))} |"
        )
    return "\n".join(rows)


def _format_sources_by_project(mapping: dict[str, list[str]]) -> str:
    if not mapping:
        return "_no sources mapped to projects_"
    lines: list[str] = []
    for project_key in sorted(mapping):
        keys = mapping[project_key]
        joined = ", ".join(f"`{k}`" for k in sorted(keys)) if keys else "_none_"
        label = project_key if project_key else "_unassigned_"
        lines.append(f"- **{label}**: {joined}")
    return "\n".join(lines)


def _format_unresolved(sources: list[str]) -> str:
    if not sources:
        return "_all registered sources are resolved_"
    return "\n".join(f"- `{s}`" for s in sorted(sources))


def _format_source_keys(keys: list[str]) -> str:
    if not keys:
        return "_no sources registered for this project_"
    return "\n".join(f"- `{k}`" for k in sorted(keys))


def _format_review_items(items: list) -> str:
    if not items:
        return "_no items currently flagged for review_"
    rows = ["| item_id | source_key | project_key | reason | suggested_action | classification |",
            "| --- | --- | --- | --- | --- | --- |"]
    for it in items:
        rows.append(
            f"| `{it.item_id}` | `{it.source_key}` | `{_kv(it.project_key)}` "
            f"| {_kv(it.reason)} | {_kv(it.suggested_action)} | {_kv(it.classification_label)} |"
        )
    return "\n".join(rows)


class ManifestRenderer:
    """Pure renderers for construction-agent projections."""

    @staticmethod
    def render_source_manifest(m: SourceManifest) -> str:
        tpl = _load_template("source_manifest")
        return tpl.format(
            display_name=m.display_name,
            source_key=m.source_key,
            project_key=_kv(m.project_key),
            kind=m.kind,
            resolution_status=m.resolution_status,
            drive_id=_kv(m.drive_id),
            web_url=_kv(m.web_url),
            generated_at=m.generated_at,
            run_id=m.run_id,
            last_sync_at=_kv(m.last_sync_at),
            delta_link_fingerprint=_kv(m.delta_link_fingerprint),
            item_counts_block=_format_counts(m.item_counts),
            sample_entries_block=_format_sample_entries(m.sample_entries, m.sample_size_cap),
            sample_size_cap=m.sample_size_cap,
            guardrails_block=_format_guardrails(m.guardrails),
        )

    @staticmethod
    def render_sync_receipt(r: SyncReceipt) -> str:
        tpl = _load_template("sync_receipt")
        return tpl.format(
            source_key=r.source_key,
            run_id=r.run_id,
            mode=r.mode,
            status=r.status,
            started_at=r.started_at,
            finished_at=_kv(r.finished_at),
            pages_seen=r.pages_seen,
            items_seen=r.items_seen,
            items_new=r.items_new,
            items_updated=r.items_updated,
            items_deleted=r.items_deleted,
            delta_link_recorded=str(r.delta_link_recorded).lower(),
            raw_delta_link_redacted=str(r.raw_delta_link_redacted).lower(),
            error_block=_format_error_block(r.error_redacted),
            guardrails_block=_format_guardrails(r.guardrails),
        )

    @staticmethod
    def render_registry_overview(o: RegistryOverview) -> str:
        tpl = _load_template("registry_overview")
        return tpl.format(
            generated_at=o.generated_at,
            project_count=o.project_count,
            source_count=o.source_count,
            projects_block=_format_projects_block(o.projects),
            sources_by_project_block=_format_sources_by_project(o.sources_by_project),
            unresolved_block=_format_unresolved(o.unresolved_sources),
            guardrails_block=_format_guardrails(o.guardrails),
        )

    @staticmethod
    def render_project_card(c: ProjectCard) -> str:
        tpl = _load_template("project_card")
        return tpl.format(
            project_key=c.project_key,
            display_name=c.display_name,
            status=c.status,
            primary_company=_kv(c.primary_company),
            source_count=c.source_count,
            last_sync_at=_kv(c.last_sync_at),
            generated_at=c.generated_at,
            source_keys_block=_format_source_keys(c.source_keys),
            totals_block=_format_counts(c.totals),
            guardrails_block=_format_guardrails(c.guardrails),
        )

    @staticmethod
    def render_review_required(n: ReviewRequiredNote) -> str:
        tpl = _load_template("review_required")
        return tpl.format(
            generated_at=n.generated_at,
            item_count=len(n.items),
            items_block=_format_review_items(n.items),
            guardrails_block=_format_guardrails(n.guardrails),
        )

    @staticmethod
    def render_document_card(d: DocumentCard) -> str:
        tpl = _load_template("document_card")
        return tpl.format(
            source_key=d.source_key,
            source_id=d.source_id,
            project_key=_kv(d.project_key),
            item_id=d.item_id,
            name=_kv(d.name),
            web_url=_kv(d.web_url),
            parent_path=_kv(d.parent_path),
            size_bytes=_kv(d.size_bytes),
            is_folder=str(d.is_folder).lower(),
            last_modified=_kv(d.last_modified),
            status=d.status,
            policy_reason=d.policy_reason,
            generated_at=d.generated_at,
            guardrails_block=_format_guardrails(d.guardrails),
        )

    @staticmethod
    def render_processing_receipt(p: ProcessingReceipt) -> str:
        tpl = _load_template("processing_receipt")
        return tpl.format(
            run_id=p.run_id,
            mode=p.mode,
            started_at=p.started_at,
            finished_at=_kv(p.finished_at),
            source_count=p.source_count,
            raw_delta_link_redacted=str(p.raw_delta_link_redacted).lower(),
            totals_block=_format_counts(p.totals),
            per_source_block=_format_per_source(p.per_source),
            error_summary_block=_format_error_summary(p.error_summary),
            guardrails_block=_format_guardrails(p.guardrails),
        )


def reset_template_cache() -> None:
    """Test hook: clear the lru_cache between tests that change templates."""
    _load_template.cache_clear()


def template_root() -> Path:
    return PathPolicy().resolve_repo_root() / "resources" / "templates"
