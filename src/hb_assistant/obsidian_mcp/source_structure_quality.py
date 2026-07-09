"""Deterministic quality findings over the persisted source-structure index.

Pure functions of the stored rows — no filesystem, no model. Produces advisory findings that the
operator reviews; ``forbidden_path_exposed`` is the one hard safety check (an absolute path must
never reach a client-facing row).
"""

from __future__ import annotations

from collections import defaultdict

from hb_assistant.obsidian_mcp.source_structure_repository import SourceStructureRepository

# Thresholds (deterministic, no clock dependency).
HIGH_FANOUT_THRESHOLD = 40
LOW_CONFIDENCE_THRESHOLD = 0.4
BACKUP_OVERRANK_CEILING = 200
VAULT_OVERRANK_CEILING = 5
MAX_LOW_CONFIDENCE_FINDINGS = 25


def _looks_absolute(path: str) -> bool:
    if not path:
        return False
    return (
        path.startswith("/")
        or path.startswith("~")
        or path.startswith("\\\\")
        or (len(path) >= 2 and path[1] == ":")  # windows drive
        or "/Users/" in path
        or "/Volumes/" in path
        or "/volume" in path  # synology volume roots
    )


def compute_findings(repo: SourceStructureRepository) -> list[dict]:
    roots = repo.all_roots()
    folders = repo.iter_folders_raw()
    findings: list[dict] = []

    folder_ids = {f["folder_id"] for f in folders}
    children_by_parent: dict[str | None, list[dict]] = defaultdict(list)
    for f in folders:
        children_by_parent[f["parent_folder_id"]].append(f)

    # --- root-level findings -------------------------------------------------------------------
    for r in roots:
        if not r.get("notes"):
            summary = repo.get_summary("root", r["root_key"])
            if not summary:
                findings.append({
                    "finding_type": "missing_root_description", "severity": "info",
                    "root_key": r["root_key"], "title": f"Root '{r['root_key']}' has no description",
                    "details": "Add a deterministic or operator summary for this root.",
                })
        if r.get("last_indexed_at") is None:
            findings.append({
                "finding_type": "stale_root", "severity": "info", "root_key": r["root_key"],
                "title": f"Root '{r['root_key']}' has never been indexed",
                "details": "No last_indexed_at timestamp recorded.",
            })
        if r.get("root_class") == "vault" and r.get("default_search_rank", 99) <= VAULT_OVERRANK_CEILING:
            findings.append({
                "finding_type": "vault_overprioritized", "severity": "warning",
                "root_key": r["root_key"],
                "title": f"Vault root '{r['root_key']}' is ranked above work roots",
                "details": "The Obsidian vault should be supplemental, not primary NAS source truth.",
                "evidence": [f"default_search_rank={r.get('default_search_rank')}"],
            })

    # --- folder-level findings -----------------------------------------------------------------
    low_conf_count = 0
    project_primary: dict[str, list[str]] = defaultdict(list)
    for f in folders:
        rel = f.get("rel_path") or ""
        # Hard safety check: no absolute path may be persisted in a client-facing row.
        if _looks_absolute(rel) or _looks_absolute(f.get("name") or ""):
            findings.append({
                "finding_type": "forbidden_path_exposed", "severity": "error",
                "root_key": f["root_key"], "folder_id": f["folder_id"],
                "title": f"Absolute-looking path in folder row: {f['name']}",
                "details": "Folder rows must carry only root-relative rel_path values.",
                "evidence": [f"rel_path={rel!r}"],
            })
        # Broken parent ref.
        parent = f.get("parent_folder_id")
        if parent is not None and parent not in folder_ids:
            findings.append({
                "finding_type": "source_ref_broken", "severity": "warning",
                "root_key": f["root_key"], "folder_id": f["folder_id"],
                "title": f"Folder '{rel}' references a missing parent",
                "details": "parent_folder_id does not resolve to an indexed folder.",
            })
        # Unclassified high-fanout.
        if f.get("folder_class") == "unknown" and f.get("child_folder_count", 0) >= HIGH_FANOUT_THRESHOLD:
            findings.append({
                "finding_type": "unclassified_high_fanout_folder", "severity": "warning",
                "root_key": f["root_key"], "folder_id": f["folder_id"],
                "title": f"Unclassified folder with {f['child_folder_count']} children: {rel}",
                "details": "A high-fan-out unclassified folder likely needs a classification rule.",
            })
        # Generated output misclassified as source-trust.
        if f.get("is_generated_output") and f.get("trust_tier") != "generated":
            findings.append({
                "finding_type": "generated_output_misclassified_as_source", "severity": "warning",
                "root_key": f["root_key"], "folder_id": f["folder_id"],
                "title": f"Generated-output folder not marked generated-trust: {rel}",
            })
        # Backup mirror overranked.
        if f.get("is_backup_mirror") and f.get("search_rank", 999) < BACKUP_OVERRANK_CEILING:
            findings.append({
                "finding_type": "backup_mirror_overranked", "severity": "warning",
                "root_key": f["root_key"], "folder_id": f["folder_id"],
                "title": f"Backup/mirror folder ranked too high: {rel}",
                "evidence": [f"search_rank={f.get('search_rank')}"],
            })
        # Project candidate without a number.
        if f.get("is_project_candidate") and not f.get("project_number"):
            findings.append({
                "finding_type": "missing_project_number_mapping", "severity": "info",
                "root_key": f["root_key"], "folder_id": f["folder_id"],
                "title": f"Project-candidate folder with no project number: {rel}",
            })
        # High-noise parent.
        noise_children = sum(1 for c in children_by_parent.get(f["folder_id"], []) if c.get("is_noise"))
        if noise_children >= 3:
            findings.append({
                "finding_type": "high_noise_folder", "severity": "info",
                "root_key": f["root_key"], "folder_id": f["folder_id"],
                "title": f"Folder '{rel}' has {noise_children} noise children",
            })
        # Low-confidence classification (capped, informational).
        if (
            f.get("folder_class") != "unknown"
            and f.get("classification_confidence", 1.0) < LOW_CONFIDENCE_THRESHOLD
            and low_conf_count < MAX_LOW_CONFIDENCE_FINDINGS
        ):
            low_conf_count += 1
            findings.append({
                "finding_type": "low_confidence_classification", "severity": "info",
                "root_key": f["root_key"], "folder_id": f["folder_id"],
                "title": f"Low-confidence classification for: {rel}",
                "evidence": [f"confidence={f.get('classification_confidence')}"],
            })
        # Collect project primaries for duplicate detection.
        if f.get("project_number") and f.get("folder_class") == "project_root":
            project_primary[f["project_number"]].append(f["folder_id"])

    # --- cross-folder findings -----------------------------------------------------------------
    for proj, ids in project_primary.items():
        if len(ids) > 1:
            findings.append({
                "finding_type": "duplicate_project_folder", "severity": "warning",
                "title": f"Project {proj} has {len(ids)} candidate primary folders",
                "details": "Multiple project_root folders map to one project number.",
                "evidence": ids[:10],
            })

    return findings
