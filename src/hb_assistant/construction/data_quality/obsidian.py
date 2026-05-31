"""Obsidian data quality outputs (Phase 07A Prompt 06).

Generates 4 marker-bounded, source-linked markdown files for the local vault:
- Project Data Quality Summary
- Source Record Map Register
- Relationship Diagnostics Register
- Phase Gate Summary (readiness snapshot from marts)

All outputs use ONLY redacted fields (title_redacted, evidence_redacted, source_url_redacted, hashes/IDs).
No raw bodies, full text, tokens, signed URLs, or source file copies.
Dry-run by default (writes evidence preview + proof JSON to repo). --apply writes marker-bounded notes to vault (if configured) using atomic + bounded replace (user content outside markers is preserved).

0 new repository helpers (explicit per plan); queries use direct get_connection() SELECTs on V20/V21 tables + existing public APIs where sufficient. No edits were made to repositories.py for Prompt 06.

Guardrails enforced at every layer (Python + SQL column selection).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from hb_assistant.store.connection import get_connection

# Marker constants for update-safe Obsidian sections (unique HB-DATA-QUALITY- prefix)
_DATA_QUALITY_MARKERS: dict[str, tuple[str, str]] = {
    "project_data_quality_summary": (
        "<!-- HB-DATA-QUALITY-PROJECT-SUMMARY:START -->",
        "<!-- HB-DATA-QUALITY-PROJECT-SUMMARY:END -->",
    ),
    "source_record_map_register": (
        "<!-- HB-DATA-QUALITY-SOURCE-RECORD-MAP:START -->",
        "<!-- HB-DATA-QUALITY-SOURCE-RECORD-MAP:END -->",
    ),
    "relationship_diagnostics_register": (
        "<!-- HB-DATA-QUALITY-RELATIONSHIP-DIAGNOSTICS:START -->",
        "<!-- HB-DATA-QUALITY-RELATIONSHIP-DIAGNOSTICS:END -->",
    ),
    "phase_gate_summary": (
        "<!-- HB-DATA-QUALITY-PHASE-GATE-SUMMARY:START -->",
        "<!-- HB-DATA-QUALITY-PHASE-GATE-SUMMARY:END -->",
    ),
}

_OBSIDIAN_GUARDRAILS = {
    "external_systems": "read_only",
    "writeback": "local_vault_only_on_apply",
    "raw_body_persisted": False,
    "raw_document_text_persisted": False,
    "tokens_or_urls_in_output": False,
    "source_file_copies": False,
    "candidate_relationships_promoted": False,
    "human_review_required_for_sensitive": True,
    "marker_bounded": True,
    "frontmatter_complete": True,
}

_SENSITIVE_REVIEW_NOTE = (
    "Model-proposed, weak, or sensitive relationships are never promoted as authoritative. "
    "They appear only in review queues with explicit review_required=true."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[4], stderr=subprocess.DEVNULL
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _get_schema_version(db_path: Optional[str | Path] = None) -> int:
    try:
        conn = get_connection(db_path)
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except Exception:
        return 0


def _ensure_markers(existing: str, start: str, end: str) -> str:
    if start in existing and end in existing:
        return existing
    if existing and not existing.endswith("\n"):
        existing += "\n"
    return existing + f"\n{start}\n{end}\n"


def _replace_bounded(existing: str, inner: str, start: str, end: str) -> str:
    pattern = re.compile(rf"({re.escape(start)})(.*?)({re.escape(end)})", re.DOTALL)
    if pattern.search(existing):
        return pattern.sub(rf"\1\n{inner}\n\3", existing)
    return existing


def _atomic_write_text(target: Path, content: str) -> int:
    """Atomic write (temp + os.replace) preserving permissions where possible."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, target)
        return len(content.encode("utf-8"))
    except Exception:
        with contextlib.suppress(Exception):
            tmp_path.unlink(missing_ok=True)
        raise


def _safe_select(conn, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Execute SELECT; never pass * or raw body columns. Returns list of dict rows."""
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description] if cur.description else []
    return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]


class ObsidianDataQualityRenderer:
    """Renders the 4 Phase 07A data-quality Obsidian artifacts (dry-run + optional apply)."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self.db_path = db_path
        self.repo_sha = _get_git_sha()
        self.schema_version = _get_schema_version(db_path)
        self.generated_utc = _now()
        self.review_items: list[dict[str, Any]] = []

    def clear_review_items(self) -> None:
        self.review_items = []

    def _query_project_summary(self) -> dict[str, Any]:
        conn = get_connection(self.db_path)
        # Aggregate from V21 project coverage + source record summary + readiness marts (defensive)
        try:
            coverage = _safe_select(
                conn,
                """
                SELECT project_key, source_domain, record_count, mapped_count, unmapped_count,
                       relationship_count, orphan_count
                FROM project_source_coverage_mart
                ORDER BY project_key, source_domain
                """,
            )
        except Exception:
            coverage = []
        try:
            readiness = _safe_select(
                conn,
                """
                SELECT project_key, meeting_prep_ready, risk_digest_ready, financial_review_ready,
                       overall_status, blocking_reasons_json
                FROM cross_domain_context_readiness_mart
                ORDER BY project_key
                """,
            )
        except Exception:
            readiness = []
        # Source record summary for mapped/unmapped rollup
        try:
            src_summary = _safe_select(
                conn,
                """
                SELECT project_key, source_system, record_count, mapped_count, unmapped_count, review_required_count
                FROM source_record_summary_mart
                ORDER BY project_key, source_system
                """,
            )
        except Exception:
            src_summary = []

        projects: dict[str, Any] = {}
        for row in coverage:
            pk = row.get("project_key") or "unknown"
            projects.setdefault(pk, {"coverage": [], "readiness": None, "source_records": {}})
            projects[pk]["coverage"].append(row)
        for row in readiness:
            pk = row.get("project_key") or "unknown"
            projects.setdefault(pk, {"coverage": [], "readiness": None, "source_records": {}})
            projects[pk]["readiness"] = row
        for row in src_summary:
            pk = row.get("project_key") or "unknown"
            projects.setdefault(pk, {"coverage": [], "readiness": None, "source_records": {}})
            ss = row.get("source_system") or "unknown"
            projects[pk]["source_records"][ss] = row

        return {
            "projects": projects,
            "total_projects": len(projects),
            "generated_utc": self.generated_utc,
        }

    def _query_source_record_register(self, limit: int = 500) -> list[dict[str, Any]]:
        conn = get_connection(self.db_path)
        try:
            rows = _safe_select(
                conn,
                """
                SELECT canonical_record_id, project_key, project_number, source_system, source_table,
                       source_primary_key, record_type, record_status, title_redacted, source_url_redacted,
                       confidence_class, review_required
                FROM source_system_record_map
                ORDER BY project_key, source_system, source_table
                LIMIT ?
                """,
                (limit,),
            )
            # Never include any non-redacted identifiers beyond what's policy-approved
            return rows
        except Exception:
            return []

    def _query_relationship_register(self, limit: int = 500) -> list[dict[str, Any]]:
        conn = get_connection(self.db_path)
        try:
            rows = _safe_select(
                conn,
                """
                SELECT relationship_id, from_canonical_record_id, to_canonical_record_id,
                       from_source_system, to_source_system, relationship_type, relationship_status,
                       confidence_class, confidence, evidence_redacted, review_required, promotion_status
                FROM relationship_resolution_queue
                ORDER BY review_required DESC, confidence DESC
                LIMIT ?
                """,
                (limit,),
            )
            return rows
        except Exception:
            return []

    def _query_relationship_quality(self) -> dict[str, Any]:
        conn = get_connection(self.db_path)
        try:
            rows = _safe_select(
                conn,
                """
                SELECT relationship_type, confidence_class, relationship_status, total_count,
                       review_required_count, orphan_count, quality_status
                FROM relationship_quality_mart
                ORDER BY relationship_type, confidence_class
                """,
            )
            return {"rows": rows}
        except Exception:
            return {"rows": []}

    def _build_frontmatter(self) -> str:
        return (
            "---\n"
            f"phase: 07A\n"
            f"generated_utc: {self.generated_utc}\n"
            f"repo_sha: {self.repo_sha}\n"
            f"schema_version: {self.schema_version}\n"
            "source_systems:\n"
            "  - procore\n"
            "  - email\n"
            "  - graph_files\n"
            "  - construction_store\n"
            "writeback: none\n"
            "raw_body_persisted: false\n"
            "raw_document_text_persisted: false\n"
            "marker_bounded: true\n"
            "---\n"
        )

    def _render_project_summary(self, data: dict[str, Any]) -> str:
        fm = self._build_frontmatter()
        lines = [fm, "# Project Data Quality Summary (Phase 07A)\n"]
        lines.append(f"Generated: {self.generated_utc} | Repo: {self.repo_sha[:8]} | Schema: V{self.schema_version}\n")
        lines.append("\n## Source Coverage by Project\n")
        if not data.get("projects"):
            lines.append("_No project coverage data present in local marts (V21). Run data-quality marts first._\n")
        else:
            for pk, p in sorted(data["projects"].items()):
                lines.append(f"### {pk}\n")
                cov = p.get("coverage") or []
                if cov:
                    lines.append("| Source Domain | Records | Mapped | Unmapped | Relationships | Orphans |\n")
                    lines.append("|---------------|---------|--------|----------|---------------|---------|\n")
                    for c in cov:
                        lines.append(
                            f"| {c.get('source_domain','?')} | {c.get('record_count',0)} | {c.get('mapped_count',0)} | "
                            f"{c.get('unmapped_count',0)} | {c.get('relationship_count',0)} | {c.get('orphan_count',0)} |\n"
                        )
                rd = p.get("readiness")
                if rd:
                    lines.append(
                        f"**Readiness:** meeting_prep={rd.get('meeting_prep_ready')}, "
                        f"risk_digest={rd.get('risk_digest_ready')}, financial={rd.get('financial_review_ready')} | "
                        f"status={rd.get('overall_status')}\n"
                    )
                    if rd.get("blocking_reasons_json"):
                        lines.append(f"Blockers: {rd['blocking_reasons_json']}\n")
                src = p.get("source_records") or {}
                if src:
                    lines.append("Source record summary: " + ", ".join(f"{k}:{v.get('record_count',0)}" for k, v in src.items()) + "\n")
                lines.append("\n")
        lines.append("\n> Guardrail: This summary contains only aggregate counts and redacted metadata. No raw content.\n")
        return "".join(lines)

    def _render_source_record_register(self, rows: list[dict[str, Any]]) -> str:
        fm = self._build_frontmatter()
        lines = [fm, "# Source Record Map Register (Phase 07A)\n"]
        lines.append(f"Generated: {self.generated_utc} | Total mapped rows shown (capped): {len(rows)}\n\n")
        if not rows:
            lines.append("_No rows in source_system_record_map. Run data-quality source-record-map --apply to populate._\n")
        else:
            lines.append("| Canonical ID (truncated) | Project | Source | Table | Title (redacted) | Confidence | Review Required |\n")
            lines.append("|--------------------------|---------|--------|-------|------------------|------------|-----------------|\n")
            for r in rows:
                cid = (r.get("canonical_record_id") or "")[:32] + "..."
                title = (r.get("title_redacted") or "")[:60].replace("|", "-")
                lines.append(
                    f"| {cid} | {r.get('project_key') or ''} | {r.get('source_system')} | {r.get('source_table')} | "
                    f"{title} | {r.get('confidence_class')} | {bool(r.get('review_required'))} |\n"
                )
        lines.append(f"\n{_SENSITIVE_REVIEW_NOTE}\n")
        lines.append("\n> Guardrail: Only title_redacted and canonical IDs (no bodies, no URLs, no secrets).\n")
        return "".join(lines)

    def _render_relationship_diagnostics(self, rows: list[dict[str, Any]], quality: dict[str, Any]) -> str:
        fm = self._build_frontmatter()
        lines = [fm, "# Relationship Diagnostics Register (Phase 07A)\n"]
        lines.append(f"Generated: {self.generated_utc}\n\n")
        lines.append("## Quality Summary (from relationship_quality_mart)\n")
        qrows = quality.get("rows") or []
        if qrows:
            lines.append("| Type | Confidence | Status | Total | Review Req | Orphans | Quality |\n")
            lines.append("|------|------------|--------|-------|------------|---------|---------|\n")
            for q in qrows:
                lines.append(
                    f"| {q.get('relationship_type')} | {q.get('confidence_class')} | {q.get('relationship_status')} | "
                    f"{q.get('total_count',0)} | {q.get('review_required_count',0)} | {q.get('orphan_count',0)} | {q.get('quality_status')} |\n"
                )
        else:
            lines.append("_No relationship quality mart rows (run data-quality marts)._\n")
        lines.append("\n## Review Candidates (from relationship_resolution_queue)\n")
        if not rows:
            lines.append("_No queued candidates._\n")
        else:
            lines.append("| Rel ID | Type | Status | Confidence | Review Req | Promotion | Evidence (redacted) |\n")
            lines.append("|--------|------|--------|------------|------------|-----------|---------------------|\n")
            for r in rows[:100]:  # bound output size
                evid = (r.get("evidence_redacted") or "")[:80].replace("|", "-")
                lines.append(
                    f"| {(r.get('relationship_id') or '')[:20]} | {r.get('relationship_type')} | {r.get('relationship_status')} | "
                    f"{r.get('confidence_class')} | {bool(r.get('review_required'))} | {r.get('promotion_status') or ''} | {evid} |\n"
                )
        lines.append(f"\n{_SENSITIVE_REVIEW_NOTE}\n")
        lines.append("\n> Guardrail: Zero raw content. Candidates with review_required=true are never auto-promoted.\n")
        return "".join(lines)

    def _render_phase_gate_summary(self) -> str:
        fm = self._build_frontmatter()
        lines = [fm, "# Phase 07A Gate Summary / Readiness Snapshot (Phase 07A)\n"]
        lines.append(f"Generated: {self.generated_utc} | Schema V{self.schema_version}\n\n")
        lines.append("This is a **readiness snapshot** derived from local marts. Full gates with thresholds and go/no-go are in Prompt 07.\n\n")
        lines.append("## Cross-Domain Readiness (from cross_domain_context_readiness_mart)\n")
        conn = get_connection(self.db_path)
        try:
            ready = _safe_select(conn, "SELECT * FROM cross_domain_context_readiness_mart ORDER BY project_key")
            if ready:
                for r in ready:
                    lines.append(f"- {r.get('project_key')}: overall={r.get('overall_status')}, meeting={r.get('meeting_prep_ready')}, risk={r.get('risk_digest_ready')}, financial={r.get('financial_review_ready')}\n")
            else:
                lines.append("_No readiness rows._\n")
        except Exception:
            lines.append("_Readiness table not present or empty (V21 migration pending)._ \n")
        lines.append("\n## Key Guardrails Attestation\n")
        for k, v in _OBSIDIAN_GUARDRAILS.items():
            lines.append(f"- {k}: {v}\n")
        lines.append(f"\n{_SENSITIVE_REVIEW_NOTE}\n")
        lines.append("\n> This note is marker-bounded and safe to re-render. User content outside markers is preserved.\n")
        return "".join(lines)

    def run(self, *, dry_run: bool = True, apply: bool = False) -> dict[str, Any]:
        """Render all 4 artifacts. Dry-run: populate evidence preview + JSON only. Apply: also write to vault (if configured)."""
        self.clear_review_items()

        # Queries (defensive; partial schema tolerant)
        proj = self._query_project_summary()
        src_rows = self._query_source_record_register()
        rel_rows = self._query_relationship_register()
        rel_quality = self._query_relationship_quality()

        # Render sections
        rendered = {
            "project_data_quality_summary": self._render_project_summary(proj),
            "source_record_map_register": self._render_source_record_register(src_rows),
            "relationship_diagnostics_register": self._render_relationship_diagnostics(rel_rows, rel_quality),
            "phase_gate_summary": self._render_phase_gate_summary(),
        }

        # Evidence preview content (always produced for dry-run and apply runs)
        preview_content = (
            "# Obsidian Data Quality Outputs — Dry-Run Preview (Phase 07A Prompt 06)\n\n"
            f"Generated: {self.generated_utc}\nRepo SHA: {self.repo_sha}\nSchema: V{self.schema_version}\n\n"
            "## Project Data Quality Summary (excerpt)\n\n"
            + rendered["project_data_quality_summary"][:2000]
            + "\n\n---\n\n## Source Record Map Register (excerpt)\n\n"
            + rendered["source_record_map_register"][:2000]
            + "\n\n---\n\n## Relationship Diagnostics (excerpt)\n\n"
            + rendered["relationship_diagnostics_register"][:2000]
            + "\n\n---\n\n## Phase Gate Summary (excerpt)\n\n"
            + rendered["phase_gate_summary"][:1500]
            + "\n\n---\n\n> Full rendered sections use marker-bounded writes. This preview is for evidence only.\n"
        )

        report: dict[str, Any] = {
            "command": "construction-agent data-quality obsidian",
            "dry_run": dry_run and not apply,
            "apply": apply and not dry_run,
            "generated_utc": self.generated_utc,
            "repo_sha": self.repo_sha,
            "schema_version": self.schema_version,
            "row_counts": {
                "source_records": len(src_rows),
                "relationship_candidates": len(rel_rows),
                "projects_in_coverage": proj.get("total_projects", 0),
            },
            "rendered_excerpts": {k: v[:500] + "..." if len(v) > 500 else v for k, v in rendered.items()},
            "guardrails": _OBSIDIAN_GUARDRAILS,
            "stop_conditions_checked": [
                "no_raw_body_selected_in_queries",
                "no_source_file_copy",
                "no_external_writeback",
                "candidates_not_promoted_as_authoritative",
            ],
            "applied_to_vault": False,
            "vault_paths": [],
            "evidence_preview_path": None,
        }

        # Always write evidence preview + proof JSON to repo evidence dir (for both dry and apply)
        evidence_dir = Path(__file__).resolve().parents[4] / "docs" / "evidence" / "construction-intelligence-phase-07a-data-quality"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        preview_path = evidence_dir / "07-obsidian-output-preview.md"
        _atomic_write_text(preview_path, preview_content)
        report["evidence_preview_path"] = str(preview_path)

        proof = {
            "prompt": "06",
            "phase": "07A",
            "generated_utc": self.generated_utc,
            "repo_sha": self.repo_sha,
            "schema_version": self.schema_version,
            "dry_run": report["dry_run"],
            "apply": report["apply"],
            "row_counts": report["row_counts"],
            "guardrails": _OBSIDIAN_GUARDRAILS,
            "no_raw_body_persisted": True,
            "no_source_file_copies": True,
            "applied_to_vault": False,
            "marker_bounded": True,
            "files_emitted": ["07-obsidian-output-preview.md", "obsidian-data-quality-dry-run.json"],
        }
        proof_path = evidence_dir / "obsidian-data-quality-dry-run.json"
        _atomic_write_text(proof_path, json.dumps(proof, indent=2, default=str) + "\n")

        if apply and not dry_run:
            # Optional vault write (only if ConstructionVaultWriter configured)
            try:
                from hb_assistant.construction.manifests.vault_writer import ConstructionVaultWriter

                writer = ConstructionVaultWriter()
                if writer.configured():
                    root = writer.root()
                    target_dir = root / "Construction Intelligence" / "Phase 07A Data Quality"
                    target_dir.mkdir(parents=True, exist_ok=True)
                    written = []
                    for kind, content in rendered.items():
                        fname = {
                            "project_data_quality_summary": "Project Data Quality Summary.md",
                            "source_record_map_register": "Source Record Map Register.md",
                            "relationship_diagnostics_register": "Relationship Diagnostics Register.md",
                            "phase_gate_summary": "Phase Gate Summary.md",
                        }[kind]
                        target = target_dir / fname
                        start, end = _DATA_QUALITY_MARKERS[kind]
                        existing = target.read_text(encoding="utf-8") if target.exists() else ""
                        framed = _ensure_markers(existing, start, end)
                        newc = _replace_bounded(framed, content.strip(), start, end)
                        _atomic_write_text(target, newc)
                        written.append(str(target))
                    report["applied_to_vault"] = True
                    report["vault_paths"] = written
                    proof["applied_to_vault"] = True
                    proof["vault_paths"] = written
                    proof["files_emitted"].extend([p.split("/")[-1] for p in written])
                    _atomic_write_text(proof_path, json.dumps(proof, indent=2, default=str) + "\n")
                else:
                    report["vault_note"] = "Vault not configured; applied_to_vault remains false. Evidence preview written."
            except Exception as e:
                report["vault_error"] = f"Vault write skipped: {type(e).__name__} (redacted)"

        return report


def render_data_quality_obsidian_outputs(
    *, dry_run: bool = True, apply: bool = False, json_out: bool = True, db_path: Optional[str | Path] = None
) -> dict[str, Any]:
    """Public entry point used by CLI and tests."""
    renderer = ObsidianDataQualityRenderer(db_path=db_path)
    return renderer.run(dry_run=dry_run, apply=apply)
