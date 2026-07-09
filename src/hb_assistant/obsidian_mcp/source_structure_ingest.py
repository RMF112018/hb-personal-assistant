"""Out-of-band ingest orchestration: parsed tree → classified records → persisted index.

Ties the parser, classifier, and repository together for the ``ingest-tree`` / ``classify`` CLI
flows. Runs OUTSIDE any request path. ``apply=False`` computes and returns a preview without writing.
"""

from __future__ import annotations

import hashlib
import json

from hb_assistant.obsidian_mcp.source_structure_classifier import classify_tree, is_noise_name
from hb_assistant.obsidian_mcp.source_structure_models import FolderRecord, SourceStructureRoot
from hb_assistant.obsidian_mcp.source_structure_repository import SourceStructureRepository
from hb_assistant.obsidian_mcp.source_structure_tree_parser import parse_tree_text


def _fingerprint(rec: FolderRecord) -> str:
    payload = json.dumps(
        {
            "class": rec.classification.folder_class,
            "fam": rec.classification.doc_family,
            "rank": rec.classification.search_rank,
            "proj": rec.classification.project_number,
            "children": rec.child_folder_count,
            "files": rec.file_count,
            "ext": rec.dominant_extensions,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _rollups(records: list[FolderRecord]) -> dict[str, dict]:
    agg: dict[str, dict] = {}
    for rec in records:
        a = agg.setdefault(
            rec.root_key, {"folder_count": 0, "file_count": 0, "noise_count": 0, "max_depth": 0}
        )
        a["folder_count"] += 1
        a["file_count"] += rec.file_count
        if rec.classification.is_noise:
            a["noise_count"] += 1
        a["max_depth"] = max(a["max_depth"], rec.depth)
    return agg


def persist_records(
    repo: SourceStructureRepository,
    roots: dict[str, SourceStructureRoot],
    records: list[FolderRecord],
) -> dict:
    """Persist classified roots + folder records + project entities/links + root rollups."""
    for root in roots.values():
        repo.upsert_root(root)

    project_links = 0
    for rec in records:
        fid = repo.upsert_folder(
            root_key=rec.root_key,
            rel_path=rec.rel_path,
            name=rec.name,
            depth=rec.depth,
            parent_rel_path=rec.parent_rel_path,
            classification=rec.classification,
            child_folder_count=rec.child_folder_count,
            file_count=rec.file_count,
            dominant_extensions=rec.dominant_extensions,
            sample_names=rec.sample_names,
            fingerprint=_fingerprint(rec),
        )
        pn = rec.classification.project_number
        if pn:
            eid = repo.upsert_entity(
                entity_type="project",
                canonical_key=pn,
                project_number=pn,
                project_name=rec.classification.project_name_hint,
                confidence=rec.classification.classification_confidence,
            )
            rel_type = (
                "primary_project_folder"
                if rec.classification.folder_class == "project_root"
                else (
                    "backup_folder" if rec.classification.is_backup_mirror
                    else "generated_output_folder" if rec.classification.is_generated_output
                    else "supporting_folder"
                )
            )
            repo.link_entity_folder(
                entity_id=eid, folder_id=fid, relationship_type=rel_type,
                confidence=rec.classification.classification_confidence,
                evidence=[f"rel_path={rec.rel_path}"],
            )
            project_links += 1

    for root_key, roll in _rollups(records).items():
        repo.update_root_rollups(root_key, **roll)

    return {
        "roots": len(roots),
        "folders": len(records),
        "project_links": project_links,
    }


def _preview(roots: dict[str, SourceStructureRoot], records: list[FolderRecord]) -> dict:
    class_counts: dict[str, int] = {}
    fam_counts: dict[str, int] = {}
    noise = backups = generated = projects = high_fanout = 0
    for rec in records:
        c = rec.classification
        class_counts[c.folder_class] = class_counts.get(c.folder_class, 0) + 1
        if c.doc_family:
            fam_counts[c.doc_family] = fam_counts.get(c.doc_family, 0) + 1
        noise += int(c.is_noise)
        backups += int(c.is_backup_mirror)
        generated += int(c.is_generated_output)
        projects += int(bool(c.project_number))
        if rec.child_folder_count >= 40:
            high_fanout += 1
    return {
        "roots": [
            {"root_key": r.root_key, "root_class": r.root_class, "trust_tier": r.trust_tier,
             "default_search_rank": r.default_search_rank}
            for r in roots.values()
        ],
        "folder_count": len(records),
        "folder_class_counts": class_counts,
        "doc_family_counts": fam_counts,
        "noise_folders": noise,
        "backup_folders": backups,
        "generated_output_folders": generated,
        "project_folders": projects,
        "high_fanout_folders": high_fanout,
    }


def generate_deterministic_summaries(repo: SourceStructureRepository) -> int:
    """Write bounded, deterministic root + project summaries (never per-folder — too many)."""
    written = 0
    roots = repo.all_roots()
    for r in roots:
        folders, total = repo.list_folders(root_key=r["root_key"], include_noise=True, limit=1)
        fam_counts: dict[str, int] = {}
        for f in repo.list_folders(root_key=r["root_key"], limit=200)[0]:
            if f.get("doc_family"):
                fam_counts[f["doc_family"]] = fam_counts.get(f["doc_family"], 0) + 1
        top_fams = ", ".join(
            f"{k} ({v})" for k, v in sorted(fam_counts.items(), key=lambda kv: -kv[1])[:5]
        ) or "none classified"
        text = (
            f"{r['display_name']} — {r['root_class']} root ({r['trust_tier']} trust). "
            f"{r.get('folder_count', total)} folders, {r.get('file_count', 0)} files. "
            f"Document families: {top_fams}."
        )
        repo.upsert_summary(
            subject_type="root", subject_id=r["root_key"], summary_text=text[:800],
            summary_kind="deterministic", confidence=0.6,
        )
        written += 1
    return written


def generate_routing_hints(repo: SourceStructureRepository) -> int:
    """Regenerate deterministic prefer/avoid routing hints per query family from persisted roots."""
    from hb_assistant.obsidian_mcp.source_structure_service import _FAMILY_ROUTING

    roots = repo.all_roots()
    by_class: dict[str, list[dict]] = {}
    for r in roots:
        by_class.setdefault(r["root_class"], []).append(r)

    total = 0
    for family, (preferred, avoided, note) in _FAMILY_ROUTING.items():
        hints: list[dict] = []
        rank = 1
        for cls in preferred:
            for r in sorted(by_class.get(cls, []), key=lambda x: x["default_search_rank"]):
                hints.append({
                    "hint_type": "prefer_root", "root_key": r["root_key"], "rank": rank,
                    "hint_text": f"Prefer '{r['root_key']}' ({cls}) for {family}."
                    + (f" {note}" if note else ""),
                    "evidence": [f"root_class={cls}"],
                })
                rank += 1
        for cls in avoided:
            for r in by_class.get(cls, []):
                hints.append({
                    "hint_type": "avoid_root", "root_key": r["root_key"], "rank": rank,
                    "hint_text": f"Avoid '{r['root_key']}' ({cls}) for {family} unless explicitly asked.",
                    "evidence": [f"root_class={cls}"],
                })
                rank += 1
        repo.replace_hints(family, hints)
        total += len(hints)
    return total


def ingest_tree_text(
    repo: SourceStructureRepository,
    text: str,
    *,
    root_key_map: dict[str, str] | None = None,
    max_nodes: int | None = None,
    apply: bool = False,
) -> dict:
    """Parse + classify a printed-tree artifact; persist when ``apply`` is True, else preview only."""
    parsed = parse_tree_text(
        text, root_key_map=root_key_map, is_noise_name=is_noise_name, max_nodes=max_nodes
    )
    roots, records = classify_tree(parsed)
    result: dict = {"parsed_totals": parsed.totals, "preview": _preview(roots, records),
                    "applied": False}
    if apply:
        result["counts"] = persist_records(repo, roots, records)
        result["applied"] = True
    return result
