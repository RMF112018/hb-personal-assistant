"""Deterministic Markdown rendering for construction-agent projections.

Templates live at ``resources/templates/*.template.md`` and use Python
``str.format`` substitution. The renderer is a pure function over Pydantic
models — same inputs → byte-identical output.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from hb_assistant.config.path_policy import PathPolicy

from .models import ProcessingReceipt, SourceManifest, SyncReceipt

_TEMPLATE_NAMES = {
    "source_manifest": "source_manifest.template.md",
    "sync_receipt": "sync_receipt.template.md",
    "processing_receipt": "processing_receipt.template.md",
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
            error_block=_format_error_block(r.error_redacted),
            guardrails_block=_format_guardrails(r.guardrails),
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
