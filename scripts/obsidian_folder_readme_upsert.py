#!/usr/bin/env python3
"""Singleton folder-README upsert + duplicate-variant reporter (Phase 10L-C).

Folder READMEs (``Source Notes/{Work,Home,Shared}/README.md`` and
``Email Archive/{Work,Home,Shared}/README.md``) are human-facing folder guides, NOT source cards: they
carry no ``source_id`` and must NEVER receive a ``__<sha>``/``__<id>`` suffix. Suffixed
``README__<id>.md`` files are *generated source cards* and are handled by the reconcile/reset tools, not
here.

This tool upserts the six singletons by EXACT path (idempotent; identical content is a no-op) and
reports — count-only — duplicate generated-README variants (``README__*.md``, ``README (n).md``, …)
found alongside them. It never deletes anything.

DRY-RUN BY DEFAULT. ``--apply`` requires exact path confirmation and a backup dir, and REFUSES to
overwrite any existing ``README.md`` that lacks this tool's generated marker (that is manual content —
protected). Writes only the six exact singleton paths; never a suffixed variant.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Marker proving this tool authored/owns the README (so apply may overwrite it). Manual READMEs lacking
# it are never overwritten.
GENERATED_MARKER = "<!-- hb-folder-readme:generated -->"

# The six singleton folder-README targets: (vault-relative path, title, purpose).
_TARGETS: tuple[tuple[str, str, str], ...] = (
    ("Source Notes/Work/README.md", "Source Notes — Work",
     "Generated work source cards (one per indexed work source). Do not edit by hand; cards regenerate."),
    ("Source Notes/Home/README.md", "Source Notes — Home",
     "Generated home source cards (one per indexed home source). Do not edit by hand; cards regenerate."),
    ("Source Notes/Shared/README.md", "Source Notes — Shared",
     "Generated shared/unknown-domain source cards. Do not edit by hand; cards regenerate."),
    ("Email Archive/Work/README.md", "Email Archive — Work",
     "Full-fidelity work email archive notes + attachments. Excluded from vault indexing/FTS."),
    ("Email Archive/Home/README.md", "Email Archive — Home",
     "Full-fidelity home email archive notes + attachments. Excluded from vault indexing/FTS."),
    ("Email Archive/Shared/README.md", "Email Archive — Shared",
     "Full-fidelity shared/unknown email archive notes + attachments. Excluded from vault indexing/FTS."),
)


class ReadmeUpsertError(Exception):
    """Refusal — printed as a controlled error, exit code 3."""


def render_readme(title: str, purpose: str) -> str:
    """Deterministic singleton-README body carrying the generated marker (idempotent content)."""
    return f"{GENERATED_MARKER}\n# {title}\n\n{purpose}\n"


def _is_generated(text: str) -> bool:
    return GENERATED_MARKER in text


def _duplicate_variants(folder: Path) -> list[str]:
    """README*.md files in ``folder`` that are NOT the exact singleton README.md (count-only names)."""
    if not folder.is_dir():
        return []
    out: list[str] = []
    for child in sorted(folder.iterdir()):
        if not child.is_file():
            continue
        name = child.name
        low = name.lower()
        if low == "readme.md":
            continue
        stem = name[:-3] if low.endswith(".md") else name
        if low.startswith("readme") and (stem.lower() != "readme"):
            out.append(name)
    return out


def plan(vault_root: Path) -> dict[str, Any]:
    """Read-only plan: per-target action (create/update/noop/protected) + duplicate-variant counts."""
    actions: list[dict[str, Any]] = []
    dup_variants: list[dict[str, Any]] = []
    for rel, title, purpose in _TARGETS:
        target = vault_root / rel
        desired = render_readme(title, purpose)
        if not target.exists():
            action = "create"
        else:
            existing = target.read_text(encoding="utf-8", errors="replace")
            if not _is_generated(existing):
                action = "protected_manual"  # lacks marker → never overwrite
            elif existing == desired:
                action = "noop"
            else:
                action = "update"
        actions.append({"rel": rel, "action": action})
        variants = _duplicate_variants(target.parent)
        if variants:
            dup_variants.append({"folder_rel": str(Path(rel).parent), "variants": variants})
    return {"actions": actions, "duplicate_variants": dup_variants}


def _atomic_write(target: Path, text: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, target)


def _safe_summary(mode: str, planned: dict[str, Any], applied: dict[str, int]) -> dict[str, Any]:
    """Path-free, count-only summary safe to commit."""
    counts: dict[str, int] = {}
    for a in planned["actions"]:
        counts[a["action"]] = counts.get(a["action"], 0) + 1
    return {
        "mode": mode,
        "target_count": len(_TARGETS),
        "action_counts": counts,
        "duplicate_variant_folder_count": len(planned["duplicate_variants"]),
        "duplicate_variant_total": sum(len(d["variants"]) for d in planned["duplicate_variants"]),
        "applied": applied,
        "note": "duplicate README variants are REPORTED only; deletion requires explicit operator auth",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Upsert singleton folder READMEs + report duplicate variants (dry-run default).")
    p.add_argument("--vault-path", required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--confirm-vault-path", default="")
    p.add_argument("--backup-dir", default="")
    p.add_argument("--json-output", default=None)
    p.add_argument("--local-sensitive-dir", default=None)
    args = p.parse_args(argv)

    vault_root = Path(args.vault_path)
    try:
        if not vault_root.is_dir():
            raise ReadmeUpsertError(f"vault path missing or not a directory: {args.vault_path!r}")
        planned = plan(vault_root)
        applied = {"created": 0, "updated": 0, "noop": 0, "protected_skipped": 0}

        if args.apply:
            if args.confirm_vault_path != args.vault_path:
                raise ReadmeUpsertError("--confirm-vault-path must exactly match --vault-path.")
            if not args.backup_dir:
                raise ReadmeUpsertError("--apply requires --backup-dir (backups of overwritten READMEs).")
            backup_root = Path(args.backup_dir)
            backup_root.mkdir(parents=True, exist_ok=True)
            for act, (rel, title, purpose) in zip(planned["actions"], _TARGETS, strict=True):
                target = vault_root / rel
                if act["action"] == "protected_manual":
                    applied["protected_skipped"] += 1
                    continue
                if act["action"] == "noop":
                    applied["noop"] += 1
                    continue
                if target.exists():  # update: back up the existing (generated) README first
                    backup_path = backup_root / rel
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    backup_path.write_text(target.read_text(encoding="utf-8", errors="replace"),
                                           encoding="utf-8")
                _atomic_write(target, render_readme(title, purpose))
                applied["created" if act["action"] == "create" else "updated"] += 1
            result = _safe_summary("apply", plan(vault_root), applied)
        else:
            result = _safe_summary("dry_run", planned, applied)
    except ReadmeUpsertError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 3

    if args.local_sensitive_dir:
        ev = Path(args.local_sensitive_dir)
        ev.mkdir(parents=True, exist_ok=True)
        (ev / f"folder-readme-{result['mode']}-plan-local-sensitive.json").write_text(
            json.dumps(planned, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json_output:
        Path(args.json_output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                                          encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
