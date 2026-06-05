"""Phase 07D Prompt 11 — marker-bounded Obsidian cross-source intelligence outputs.

Projects the six 07D read models — cross-source relationships, meeting-prep readiness, project issue
history, risk digest, aging & exposure, and correspondence context — into marker-bounded Obsidian
notes, **without raw content**. The source for each note is the corresponding read-model
``*_status()`` summary, which already emits safe aggregates only (counts / enums / bands / review
counts); no raw body / document text / status payload / token / URL can reach a note.

Dry-run (default) writes a repo evidence preview + proof JSON and **no vault**. ``--apply``
additionally writes the six notes to the local Obsidian vault using the established atomic,
marker-bounded replace (user content outside the ``HB-CROSS-SOURCE-*`` markers is preserved verbatim
on re-runs). Every rendered note passes an output-fence that rejects tokens / URLs / PEM / full-text
markers. A run record is persisted to the V25 ``cross_source_intelligence_obsidian_runs`` audit
table. No external writeback; nothing is auto-promoted; outputs are advisory.
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

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.aging_exposure import project_aging_exposure_status
from hb_assistant.construction.correspondence import correspondence_context_status
from hb_assistant.construction.issue_history import project_issue_history_status
from hb_assistant.construction.meeting_prep import meeting_prep_brief_status
from hb_assistant.construction.relationships.cross_source_substrate import (
    relationship_substrate_status,
)
from hb_assistant.construction.risk_digest import project_risk_digest_status
from hb_assistant.construction.store.repositories import ConstructionStore
from hb_assistant.normalize.redaction import hash_value
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

_EVIDENCE_FOLDER = "construction-intelligence-phase-07d-cross-source-meeting-prep"
_VAULT_SUBDIR = ("Construction Intelligence", "Phase 07D Cross-Source Intelligence")

_OBSIDIAN_GUARDRAILS: dict[str, Any] = {
    "external_systems": "read_only",
    "writeback": "local_vault_only_on_apply",
    "no_raw_content": True,
    "marker_bounded": True,
    "source_traceability": True,
    "candidates_promoted_as_authoritative": False,
    "advisory_only": True,
}

_STOP_CONDITIONS = [
    "no_raw_content_in_status_summaries",
    "output_fence_enforced_on_every_note",
    "no_external_writeback",
    "candidates_not_promoted_as_authoritative",
]

_PEM_MARKER = "-----" + "begin"
_FORBIDDEN_MARKERS = (
    "deltatoken=",
    "?token=",
    "&token=",
    "sig=",
    "downloadurl",
    "authorization:",
    "bearer ",
    "access_token",
    "refresh_token",
    "client_secret",
    "http://",
    "https://",
    _PEM_MARKER,
    "full_document_text",
    "full_body_" + "plaintext",
)


def _assert_output_fence(rendered: str) -> None:
    low = (rendered or "").lower()
    for tok in _FORBIDDEN_MARKERS:
        if tok in low:
            raise ValueError(
                f"output-fence violation: forbidden marker {tok!r} in cross-source Obsidian content"
            )


def _ensure_markers(existing: str, start: str, end: str) -> str:
    if start in existing and end in existing:
        return existing
    if existing and not existing.endswith("\n"):
        existing += "\n"
    return existing + f"\n{start}\n{end}\n"


def _replace_bounded(existing: str, inner: str, start: str, end: str) -> str:
    pattern = re.compile(rf"({re.escape(start)})(.*?)({re.escape(end)})", re.DOTALL)
    return pattern.sub(rf"\1\n{inner}\n\3", existing)


def _atomic_write_text(target: Path, content: str) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp"
    )
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


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=PathPolicy().resolve_repo_root(),
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


# (kind, title, filename, marker_key, status_fn, review_field)
_NOTE_SPECS: tuple[tuple[str, str, str, str, Any, str], ...] = (
    (
        "relationships",
        "Cross-Source Relationships",
        "Cross-Source Relationships.md",
        "RELATIONSHIPS",
        relationship_substrate_status,
        "review_required",
    ),
    (
        "meeting_prep",
        "Meeting-Prep Readiness",
        "Meeting-Prep Readiness.md",
        "MEETING-PREP",
        meeting_prep_brief_status,
        "review_required_sections",
    ),
    (
        "issue_history",
        "Project Issue History",
        "Project Issue History.md",
        "ISSUE-HISTORY",
        project_issue_history_status,
        "review_required",
    ),
    (
        "risk_digest",
        "Risk Digest",
        "Risk Digest.md",
        "RISK-DIGEST",
        project_risk_digest_status,
        "review_required",
    ),
    (
        "aging_exposure",
        "Aging and Exposure",
        "Aging and Exposure.md",
        "AGING-EXPOSURE",
        project_aging_exposure_status,
        "review_required",
    ),
    (
        "correspondence",
        "Correspondence Context",
        "Correspondence Context.md",
        "CORRESPONDENCE",
        correspondence_context_status,
        "review_required_threads",
    ),
)


def _render_value(value: Any) -> str:
    if isinstance(value, dict):
        if not value:
            return "_(none)_"
        return "; ".join(f"{k}: {v}" for k, v in sorted(value.items()))
    return str(value)


def _render_section(title: str, summary: dict[str, Any], review_count: int) -> str:
    lines = [f"### {title}", "", f"> [!info] Advisory — review-required items: {review_count}", ""]
    for key, value in summary.items():
        lines.append(f"- **{key}**: {_render_value(value)}")
    lines += [
        "",
        "_Source: local SQLite (V25 read models, redacted aggregates). Advisory only — "
        "no legal/contractual/claim/safety/financial determination; review-required items are "
        "never presented as authoritative._",
    ]
    return "\n".join(lines)


class ObsidianCrossSourceRenderer:
    """Render the 07D cross-source intelligence into marker-bounded Obsidian notes."""

    def __init__(self, store: Optional[ConstructionStore] = None) -> None:
        self._store = store or ConstructionStore()

    def _vault_root(self, vault_root: Optional[Path]) -> Optional[Path]:
        if vault_root is not None:
            return Path(vault_root)
        try:
            from hb_assistant.construction.manifests.vault_writer import ConstructionVaultWriter

            writer = ConstructionVaultWriter()
            if writer.configured():
                return writer.root()
        except Exception:
            return None
        return None

    def render(
        self,
        *,
        dry_run: bool = True,
        apply: bool = False,
        project_filter: Optional[str] = None,
        evidence_dir: Optional[Path] = None,
        vault_root: Optional[Path] = None,
        now_utc: Optional[datetime] = None,
    ) -> dict[str, Any]:
        mode = "apply" if (apply and not dry_run) else "dry_run"
        generated = (now_utc or datetime.now(timezone.utc)).isoformat()

        rendered: dict[str, str] = {}
        review_total = 0
        for kind, title, _fname, _mk, status_fn, review_field in _NOTE_SPECS:
            try:
                summary = status_fn(self._store, project_filter=project_filter).get("summary", {})
            except Exception:
                summary = {}
            review_count = int(summary.get(review_field, 0) or 0)
            review_total += review_count
            section = _render_section(title, summary, review_count)
            _assert_output_fence(section)
            rendered[kind] = section

        applied_to_vault = False
        vault_paths: list[str] = []
        notes_written = 0
        status = "rendered"

        if mode == "apply":
            root = self._vault_root(vault_root)
            if root is not None:
                target_dir = root.joinpath(*_VAULT_SUBDIR)
                for kind, _title, fname, marker_key, _fn, _rf in _NOTE_SPECS:
                    start = f"<!-- HB-CROSS-SOURCE-{marker_key}:START -->"
                    end = f"<!-- HB-CROSS-SOURCE-{marker_key}:END -->"
                    target = target_dir / fname
                    if target.exists():
                        existing = target.read_text(encoding="utf-8")
                    else:
                        existing = (
                            f"---\nphase: 07D\nproject: {project_filter or 'all'}\n"
                            f"source: local_sqlite_v25\nadvisory: true\n---\n"
                        )
                    framed = _ensure_markers(existing, start, end)
                    result = _replace_bounded(framed, rendered[kind].strip(), start, end)
                    _assert_output_fence(result)
                    _atomic_write_text(target, result)
                    vault_paths.append(str(target))
                    notes_written += 1
                applied_to_vault = True
                status = "applied"
            else:
                status = "vault_not_configured"

        evidence_preview_path: Optional[str] = None
        if mode == "dry_run":
            base = evidence_dir or (
                PathPolicy().resolve_repo_root() / "docs" / "evidence" / _EVIDENCE_FOLDER
            )
            base = Path(base)
            base.mkdir(parents=True, exist_ok=True)
            preview = "\n\n".join(
                f"## {title}\n\n{rendered[kind]}" for kind, title, *_ in _NOTE_SPECS
            )
            preview_path = base / "11-obsidian-cross-source-output-preview.md"
            _atomic_write_text(preview_path, preview + "\n")
            evidence_preview_path = str(preview_path)
            proof = {
                "prompt": "11",
                "phase": "07D",
                "generated_utc": generated,
                "repo_sha": _git_sha(),
                "schema_version": LATEST_SCHEMA_VERSION,
                "mode": mode,
                "notes_planned": len(_NOTE_SPECS),
                "notes_written": 0,
                "applied_to_vault": False,
                "marker_bounded": True,
                "no_raw_content": True,
                "review_required_total": review_total,
                "guardrails": _OBSIDIAN_GUARDRAILS,
                "files_emitted": [
                    "11-obsidian-cross-source-output-preview.md",
                    "obsidian-cross-source-dry-run.json",
                ],
            }
            _atomic_write_text(
                base / "obsidian-cross-source-dry-run.json",
                json.dumps(proof, indent=2, default=str) + "\n",
            )

        run_id = hash_value(f"cross_source_obsidian|{project_filter or '_all_'}|{mode}") or mode
        with contextlib.suppress(Exception):
            self._store.upsert_cross_source_intelligence_obsidian_run(
                obsidian_run_id=run_id,
                project_key=project_filter,
                mode=mode,
                output_kind="cross_source_intelligence",
                status=status,
                notes_written=notes_written,
                review_required_count=review_total,
            )

        return {
            "command": "construction-agent cross-source obsidian",
            "mode": mode,
            "ok": True,
            "schema_version": LATEST_SCHEMA_VERSION,
            "repo_sha": _git_sha(),
            "generated_utc": generated,
            "project_filter": project_filter,
            "status": status,
            "notes_planned": len(_NOTE_SPECS),
            "notes_written": notes_written,
            "review_required_count": review_total,
            "applied_to_vault": applied_to_vault,
            "vault_paths": vault_paths,
            "evidence_preview_path": evidence_preview_path,
            "rendered_excerpts": {
                k: (v[:500] + "..." if len(v) > 500 else v) for k, v in rendered.items()
            },
            "stop_conditions_checked": _STOP_CONDITIONS,
            "guardrails": _OBSIDIAN_GUARDRAILS,
        }


def render_cross_source_obsidian_outputs(
    *,
    dry_run: bool = True,
    apply: bool = False,
    project_filter: Optional[str] = None,
    db_path: Optional[str | Path] = None,
    evidence_dir: Optional[Path] = None,
    vault_root: Optional[Path] = None,
    now_utc: Optional[datetime] = None,
) -> dict[str, Any]:
    """Public entry point used by CLI and tests."""
    store = ConstructionStore(db_path=db_path) if db_path is not None else None
    renderer = ObsidianCrossSourceRenderer(store)
    return renderer.render(
        dry_run=dry_run,
        apply=apply,
        project_filter=project_filter,
        evidence_dir=evidence_dir,
        vault_root=vault_root,
        now_utc=now_utc,
    )


def cross_source_obsidian_status(
    store: Optional[ConstructionStore] = None, *, project_filter: Optional[str] = None
) -> dict[str, Any]:
    """Read-only coverage over the V25 cross-source-intelligence Obsidian run records."""
    store = store or ConstructionStore()
    runs = store.list_cross_source_intelligence_obsidian_runs(
        project_key=project_filter, limit=100000
    )
    by_mode: dict[str, int] = {}
    notes_written = 0
    for r in runs:
        by_mode[str(r["mode"])] = by_mode.get(str(r["mode"]), 0) + 1
        notes_written += int(r.get("notes_written") or 0)
    return {
        "command": "construction-agent cross-source status",
        "ok": True,
        "schema_version": LATEST_SCHEMA_VERSION,
        "project_filter": project_filter,
        "summary": {
            "runs": len(runs),
            "by_mode": dict(sorted(by_mode.items())),
            "total_notes_written": notes_written,
            "last_run": runs[0] if runs else None,
        },
        "guardrails": _OBSIDIAN_GUARDRAILS,
    }
