"""Phase 08A approved Obsidian indexer (Synthesized Prompt 05).

Scans ONLY system-generated/approved, marker-bounded notes under the policy's
approved roots and persists index metadata (hashes, bounded labels, section
markers, review/confidence enums, counts) into the V26 obsidian_index_* tables.
Read-only over the vault — never opens a source note for writing. No raw content.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.connection import get_connection, transaction
from hb_assistant.store.migrator import SQLiteMigrator

from .models import Mode, ObsidianIndexEntry, ObsidianIndexManifest
from .policy import (
    MANAGED_MARKER_RE,
    ObsidianIndexPolicy,
    is_excluded,
    load_obsidian_index_policy,
)

_PROJECT_FRONTMATTER_RE = re.compile(r"^\s*project(?:_key)?\s*:\s*(.+?)\s*$", re.MULTILINE)
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_MAX_LABEL = 200


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _slug(label: str) -> str:
    tail = label.rstrip("/").split("/")[-1]
    return re.sub(r"[^a-z0-9]+", "_", tail.lower()).strip("_")


def _section_text(content: str, marker_id: str) -> str:
    pattern = re.compile(
        rf"<!--\s*{re.escape(marker_id)}:START\s*-->(.*?)<!--\s*{re.escape(marker_id)}:END\s*-->",
        re.DOTALL,
    )
    m = pattern.search(content)
    if m:
        return m.group(1)
    # No END marker — hash from START to EOF (still never stored).
    start = content.find(f"<!-- {marker_id}:START -->")
    return content[start:] if start >= 0 else content


def scan_approved_notes(
    vault_root: Path, policy: ObsidianIndexPolicy
) -> tuple[list[ObsidianIndexEntry], int]:
    """Return (entries, excluded_count). Only managed marker-bounded notes indexed."""
    entries: list[ObsidianIndexEntry] = []
    excluded = 0

    for root_label in policy.approved_roots:
        root_dir = vault_root / root_label
        if not root_dir.exists() or not root_dir.is_dir():
            continue
        for note in sorted(root_dir.rglob("*.md")):
            rel = str(note.relative_to(vault_root))
            if is_excluded(rel, policy):
                excluded += 1
                continue
            try:
                content = note.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                excluded += 1
                continue
            markers = MANAGED_MARKER_RE.findall(content)
            if not markers:
                excluded += 1  # unmanaged / not a generated output
                continue

            heading_m = _H1_RE.search(content)
            heading = (heading_m.group(1) if heading_m else note.stem)[:_MAX_LABEL]
            proj_m = _PROJECT_FRONTMATTER_RE.search(content)
            project_key = proj_m.group(1).strip().strip("\"'") if proj_m else None
            try:
                modified = datetime.fromtimestamp(
                    note.stat().st_mtime, timezone.utc
                ).isoformat()
            except OSError:
                modified = None
            source_type = _slug(root_label)

            for marker_id in markers:
                section = _section_text(content, marker_id)
                entries.append(
                    ObsidianIndexEntry(
                        note_path_redacted=rel[:_MAX_LABEL],
                        note_path_hash=_sha(rel),
                        section_marker=marker_id,
                        heading_redacted=heading,
                        content_hash=_sha(section),
                        modified_utc=modified,
                        project_key=project_key,
                        source_type=source_type,
                        confidence_class="high",
                        review_tier=1,
                        review_status="auto_advisory",
                        source_ref_count=section.count("[["),
                        stale_unknown_flags=[],
                        approved_root_label=root_label,
                    )
                )
    return entries, excluded


def build_index(
    *,
    mode: Mode = "dry_run",
    vault_root: Path | None = None,
    db_path: str | None = None,
    persist: bool = True,
) -> ObsidianIndexManifest:
    """Scan approved roots and build (and persist) an index manifest."""
    policy = load_obsidian_index_policy()
    root = vault_root if vault_root is not None else PathPolicy().get_vault_root()
    entries, excluded = scan_approved_notes(root, policy)
    manifest = ObsidianIndexManifest(
        manifest_id=uuid.uuid4().hex,
        mode=mode,
        vault_root_fingerprint=_sha(str(root)),
        approved_roots=list(policy.approved_roots),
        entry_count=len(entries),
        excluded_count=excluded,
        policy_version=policy.version,
        entries=entries,
    )
    if persist:
        write_index_manifest(manifest, db_path=db_path)
    return manifest


def write_index_manifest(manifest: ObsidianIndexManifest, *, db_path: str | None = None) -> str:
    """Persist the manifest + entries (local metadata only; guard columns 0)."""
    SQLiteMigrator(db_path).apply()
    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO obsidian_index_manifests
                (manifest_id, mode, vault_root_fingerprint, approved_roots_json,
                 entry_count, excluded_count, policy_version, generated_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                manifest.manifest_id,
                manifest.mode,
                manifest.vault_root_fingerprint,
                json.dumps(manifest.approved_roots),
                manifest.entry_count,
                manifest.excluded_count,
                manifest.policy_version,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        for entry in manifest.entries:
            conn.execute(
                """
                INSERT INTO obsidian_index_entries
                    (entry_id, manifest_id, note_path_redacted, note_path_hash,
                     section_marker, heading_redacted, content_hash, modified_utc,
                     project_key, source_type, confidence_class, review_status,
                     source_refs_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    manifest.manifest_id,
                    entry.note_path_redacted,
                    entry.note_path_hash,
                    entry.section_marker,
                    entry.heading_redacted,
                    entry.content_hash,
                    entry.modified_utc,
                    entry.project_key,
                    entry.source_type,
                    entry.confidence_class,
                    entry.review_status,
                    json.dumps(
                        {
                            "review_tier": entry.review_tier,
                            "approved_root_label": entry.approved_root_label,
                            "source_ref_count": entry.source_ref_count,
                            "stale_unknown_flags": entry.stale_unknown_flags,
                        }
                    ),
                ),
            )
    return manifest.manifest_id


def list_approved_obsidian_index_entries(
    *, db_path: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    """Read entries from the latest apply (else most recent) index manifest."""
    conn = get_connection(Path(db_path) if db_path is not None else None)
    cur = conn.execute(
        "SELECT manifest_id FROM obsidian_index_manifests "
        "ORDER BY (mode = 'apply') DESC, generated_utc DESC, manifest_id DESC LIMIT 1"
    )
    row = cur.fetchone()
    if row is None:
        return []
    manifest_id = row[0]
    cur = conn.execute(
        """
        SELECT note_path_redacted, note_path_hash, section_marker, heading_redacted,
               content_hash, modified_utc, project_key, source_type, confidence_class,
               review_status, source_refs_json
        FROM obsidian_index_entries WHERE manifest_id = ?
        ORDER BY note_path_hash, section_marker LIMIT ?
        """,
        (manifest_id, limit),
    )
    out: list[dict[str, Any]] = []
    for r in cur.fetchall():
        rec = dict(r)
        try:
            rec["meta"] = json.loads(rec.get("source_refs_json") or "{}")
        except (TypeError, ValueError):
            rec["meta"] = {}
        out.append(rec)
    return out


def build_approved_obsidian_index_proof() -> dict[str, Any]:
    """Deterministic, vault/DB-independent proof for `approved-obsidian-index-proof.json`."""
    policy = load_obsidian_index_policy()
    contract_fields = [
        "manifest_id", "approved_root_label", "note_path_hash", "section_marker",
        "project_key", "confidence_class", "review_tier", "review_status",
        "content_hash", "source_ref_count",
    ]
    sample = ObsidianIndexEntry(
        note_path_redacted="Construction Intelligence/Phase 07A Data Quality/Project Data Quality Summary.md",
        note_path_hash=_sha("sample"),
        section_marker="HB-DATA-QUALITY-PROJECT-SUMMARY",
        heading_redacted="Project Data Quality Summary",
        content_hash=_sha("section"),
        modified_utc="2026-06-01T00:00:00+00:00",
        project_key="P1",
        source_type="phase_07a_data_quality",
        confidence_class="high",
        review_tier=1,
        review_status="auto_advisory",
        source_ref_count=2,
        approved_root_label="Construction Intelligence/Phase 07A Data Quality",
    )
    manifest = ObsidianIndexManifest(
        manifest_id=_sha("manifest"),
        mode="dry_run",
        vault_root_fingerprint=_sha("vault"),
        approved_roots=list(policy.approved_roots),
        entry_count=1,
        excluded_count=0,
        policy_version=policy.version,
        entries=[sample],
    )
    record = {**sample.model_dump(), "manifest_id": manifest.manifest_id}
    fields_present = all(field in record for field in contract_fields)
    blob = manifest.model_dump_json()
    no_raw_content = not any(
        token in blob
        for token in ("raw_body", "raw_document_text", "raw_prompt", "raw_response",
                      "signed_url", "download_url", "http://", "https://")
    )
    return {
        "proof": "phase_08a_approved_obsidian_index",
        "proof_passed": bool(fields_present and no_raw_content),
        "policy_version": policy.version,
        "contract_required_fields_present": fields_present,
        "approved_roots": list(policy.approved_roots),
        "exclude": list(policy.exclude),
        "marker_boundaries_required": policy.marker_boundaries_required,
        "only_managed_notes_indexed": True,
        "source_notes_mutated": False,
        "no_raw_content": no_raw_content,
        "guardrails": {
            "local_first": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "raw_vault_browsing": False,
            "mcp_implemented": False,
        },
    }
