#!/usr/bin/env python3
"""Quarantine-first reset of the Obsidian vault into a clean Work/Home Markdown-first structure.

DRY-RUN BY DEFAULT. Nothing is renamed/created/deleted unless ``--apply`` (reset) or
``--delete-quarantine`` (deletion) is passed with the required confirmations.

The reset NEVER deletes the old vault as a first move: ``--apply`` *renames* the current vault aside
to ``<name> - QUARANTINED - <session>`` and creates a fresh vault at the exact same path. It NEVER
touches anything outside the vault path (external OneDrive/Synology source roots are untouched —
the script only ever operates within ``--vault-path``).

Safety model
------------
* Refuses unsafe vault paths (``/``, the home dir, ``~/Documents``, empty) and — outside tests —
  any path that is not exactly the configured default (``--allow-nonstandard-vault-path`` is the
  explicit test/operator escape hatch used with temp fixture paths).
* Refuses ``--apply`` if a backend is listening on port 8000 (a running watcher must not race the
  reset). Dry-run tolerates a running backend only with ``--allow-running-backend``.
* ``--apply`` REFUSES unless a *full recursive manifest* for the exact vault path + this
  ``--session-id`` already exists (forces a review step — apply never silently generates it).
* ``--delete-quarantine`` requires ``--confirm-path "<exact quarantine path>"``.

Manifests
---------
* Summary manifest (top-level entries) — fast dry-run preview, written every run.
* Full recursive manifest (``--full-manifest`` or implied review step) — one record per file with
  relative path, kind, extension, size, mtime, top-level folder, classification, planned
  disposition. Never hashes file contents (safe over multi-GB trees).
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_VAULT_PATH = "/Users/bobbyfetting/Documents/Obsidian Vault"
BACKEND_PORT = 8000

# Paths that must never be treated as a vault (catastrophic if renamed/deleted).
_UNSAFE_EXACT = {
    "",
    "/",
    str(Path.home()),
    str(Path.home() / "Documents"),
    "/Users/bobbyfetting",
    "/Users/bobbyfetting/Documents",
}

# Never carried into the clean vault (software/runtime/plugin state + raw corpuses).
_NEVER_COPY_TOP = {".git", ".venv", ".smart-env", ".trash", "__pycache__", "node_modules"}
# A conservative whitelist of safe .obsidian settings copied only with --copy-safe-obsidian-settings.
_SAFE_OBSIDIAN_SETTINGS = {"app.json", "appearance.json", "hotkeys.json"}

_MARKDOWN_EXTS = {"md", "markdown"}
_CORPUS_EXTS = {
    "pdf", "dwg", "rvt", "xer", "mp4", "mov", "avi", "zip", "rar", "7z", "msg", "eml",
    "xlsx", "xls", "pptx", "ppt", "docx", "doc", "png", "jpg", "jpeg", "tif", "tiff",
    "ajson", "crdownload", "part",
}

# Clean Work/Home Markdown-first target tree (relative dirs created under the new vault).
TARGET_TREE: tuple[str, ...] = (
    "00 Inbox",
    "Work/00 Dashboard", "Work/01 Projects", "Work/02 Meetings", "Work/03 Decisions",
    "Work/04 Actions", "Work/05 People", "Work/06 Companies", "Work/07 Knowledge",
    "Work/08 Templates", "Work/09 Archive",
    "Home/00 Dashboard", "Home/01 Personal Admin", "Home/02 Family", "Home/03 Home Projects",
    "Home/04 Finance", "Home/05 Health Fitness", "Home/06 Travel", "Home/07 Learning",
    "Home/08 People", "Home/09 Archive",
    "Source Notes/Work", "Source Notes/Home", "Source Notes/Shared",
    "Daily/Work", "Daily/Home",
    "MOCs/Work", "MOCs/Home", "MOCs/Shared",
    "Templates/Source Cards", "Templates/Meetings", "Templates/Decisions", "Templates/Projects",
    "Templates/Daily", "Templates/People", "Templates/Companies",
    "Attachments",
    "90 Archive",
    "99 System/Manifests", "99 System/Receipts", "99 System/Runbooks",
)

# README seeds for the major folders (purpose + what does NOT belong there).
_READMES: dict[str, str] = {
    ".": (
        "# Obsidian Vault — Work/Home Second Brain\n\n"
        "Curated Markdown intelligence only. Raw project corpuses (PDFs, drawings, models, video, "
        "archives) stay in external source roots and are surfaced as generated cards under "
        "`Source Notes/`. Do NOT dump non-Markdown files or software/runtime artifacts here.\n"
    ),
    "00 Inbox": "# Inbox\n\nUnsorted capture. Triage into Work/ or Home/ promptly. Not a long-term store.\n",
    "Work": "# Work\n\nProfessional intelligence: projects, meetings, decisions, actions, people, companies, knowledge.\n",
    "Home": "# Home\n\nPersonal intelligence: admin, family, home projects, finance, health, travel, learning.\n",
    "Source Notes": (
        "# Source Notes\n\nGENERATED source cards/summaries (one per external file), subdivided by "
        "domain: `Work/`, `Home/`, `Shared/`. Managed by the source-intelligence system — do not "
        "hand-edit generated cards; they are refreshed/retired by the watcher.\n"
    ),
    "Daily": "# Daily\n\nDaily notes split by domain (`Work/`, `Home/`).\n",
    "MOCs": "# MOCs\n\nMaps of Content / dashboards linking projects, people, decisions (`Work/`, `Home/`, `Shared/`).\n",
    "Templates": "# Templates\n\nNote templates (source cards, meetings, decisions, projects, daily, people, companies).\n",
    "Attachments": "# Attachments\n\nKeep empty or near-empty. Lightweight, intentional, Markdown-referenced files only — NOT a corpus dump.\n",
    "90 Archive": "# Archive\n\nRetired notes kept for reference. Not active working material.\n",
    "99 System": "# System\n\nReset manifests, receipts, and runbooks. Operational, not knowledge content.\n",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _path_sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]


def _backend_listening(port: int = BACKEND_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _classify(top_folder: str, rel_path: str, is_dir: bool) -> str:
    name = top_folder.lower()
    if name in _NEVER_COPY_TOP or name.startswith("."):
        return "system_artifact"
    if is_dir:
        return "directory"
    ext = Path(rel_path).suffix.lower().lstrip(".")
    if ext in _MARKDOWN_EXTS:
        return "markdown"
    if ext in _CORPUS_EXTS:
        return "corpus"
    return "non_markdown_other"


def _planned_disposition(classification: str) -> str:
    # The reset is wholesale: every current entry is renamed aside into the quarantine. Nothing is
    # copied into the clean vault except optional whitelisted .obsidian settings.
    return "move_to_quarantine"


def _entry_record(vault: Path, abs_path: Path, *, kind: str) -> dict[str, Any] | None:
    """Build one manifest record. Always uses ``os.lstat`` (NEVER follows a symlink), so metadata is
    of the entry itself — never of a (possibly external) symlink target. ``kind`` is one of
    file/dir/symlink; a symlink is classified as ``symlink`` and is never followed."""
    try:
        rel = str(abs_path.relative_to(vault))
    except ValueError:
        return None
    top = rel.replace("\\", "/").split("/", 1)[0]
    classification = "symlink" if kind == "symlink" else _classify(top, rel, is_dir=(kind == "dir"))
    size = None
    mtime = None
    try:
        st = os.lstat(abs_path)  # lstat: never follows the link
        mtime = st.st_mtime_ns
        if kind != "dir":
            size = st.st_size
    except OSError:
        pass
    return {
        "rel_path": rel, "kind": kind,
        "ext": "" if kind in ("dir", "symlink") else Path(rel).suffix.lower().lstrip("."),
        "size_bytes": size, "mtime_ns": mtime, "top_folder": top,
        "classification": classification,
        "planned_disposition": _planned_disposition(classification),
    }


def _summary_manifest(vault: Path) -> list[dict[str, Any]]:
    """Fast top-level preview — directories are not size-summed (no deep walk). Symlinks are tagged
    and never followed (``is_symlink`` checked before ``is_dir``)."""
    rows: list[dict[str, Any]] = []
    for entry in sorted(vault.iterdir(), key=lambda p: p.name):
        if entry.is_symlink():
            kind = "symlink"
        elif entry.is_dir():
            kind = "dir"
        else:
            kind = "file"
        rec = _entry_record(vault, entry, kind=kind)
        if rec is not None:
            rows.append(rec)
    return rows


def _full_manifest_records(vault: Path):
    """Yield one record per entry (recursive). Symlinks are recorded as symlinks and NEVER followed;
    the walk does not descend into symlinked directories, so it never traverses outside the vault.
    No content hashing (safe over multi-GB trees)."""
    for dirpath, dirnames, filenames in os.walk(vault, followlinks=False):
        # Record symlinked directories as symlink entries, then prune them so the walk never
        # descends into them (a dir symlink could point outside the vault).
        symlink_dirs = [d for d in dirnames if os.path.islink(os.path.join(dirpath, d))]
        for d in symlink_dirs:
            rec = _entry_record(vault, Path(dirpath) / d, kind="symlink")
            if rec is not None:
                yield rec
        if symlink_dirs:
            dirnames[:] = [d for d in dirnames if d not in symlink_dirs]
        for fname in filenames:
            abs_path = Path(dirpath) / fname
            kind = "symlink" if os.path.islink(abs_path) else "file"
            rec = _entry_record(vault, abs_path, kind=kind)
            if rec is not None:
                yield rec


def _full_manifest_path(evidence_dir: Path, session_id: str) -> Path:
    return evidence_dir / f"vault-reset-manifest-full-{session_id}.jsonl"


def _summary_manifest_path(evidence_dir: Path, session_id: str) -> Path:
    return evidence_dir / f"vault-reset-manifest-summary-{session_id}.json"


def _write_full_manifest(vault: Path, evidence_dir: Path, session_id: str) -> tuple[Path, int]:
    out = _full_manifest_path(evidence_dir, session_id)
    meta = {
        "kind": "manifest_meta", "manifest_type": "full", "vault_path": str(vault),
        "vault_path_sha256": _path_sha(vault), "session_id": session_id,
        "generated_at": _now_iso(),
    }
    count = 0
    with out.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(meta, sort_keys=True) + "\n")
        for rec in _full_manifest_records(vault):
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
            count += 1
    return out, count


def _quarantine_path(vault: Path, session_id: str) -> Path:
    return vault.parent / f"{vault.name} - QUARANTINED - {session_id}"


class ResetError(Exception):
    """Refusal — printed as a controlled error, exit code 3."""


def _validate_vault_path(vault: Path, *, allow_nonstandard: bool) -> None:
    resolved = str(vault)
    # An empty/"." arg becomes Path(".") (the cwd) — refuse it outright.
    if resolved.strip() in ("", "."):
        raise ResetError("Refusing empty/'.' vault path.")
    if resolved in _UNSAFE_EXACT or resolved.rstrip("/") in _UNSAFE_EXACT:
        raise ResetError(f"Refusing unsafe vault path: {resolved!r}")
    if not allow_nonstandard and resolved != DEFAULT_VAULT_PATH:
        raise ResetError(
            f"Refusing non-standard vault path {resolved!r} (expected {DEFAULT_VAULT_PATH!r}). "
            "Pass --allow-nonstandard-vault-path to override (tests/operator-explicit only)."
        )


def _verify_full_manifest_for_apply(vault: Path, evidence_dir: Path, session_id: str) -> Path:
    path = _full_manifest_path(evidence_dir, session_id)
    if not path.is_file():
        raise ResetError(
            f"--apply requires a full recursive manifest for this session first. Expected: {path}. "
            f"Run a dry-run with --full-manifest --session-id {session_id} and review it."
        )
    with path.open("r", encoding="utf-8") as fh:
        first = fh.readline()
    try:
        meta = json.loads(first)
    except Exception as exc:
        raise ResetError(f"Full manifest is unreadable: {path} ({exc})") from exc
    if meta.get("vault_path") != str(vault) or meta.get("vault_path_sha256") != _path_sha(vault):
        raise ResetError(
            f"Full manifest {path} was created for a different vault path "
            f"({meta.get('vault_path')!r}) than the apply target ({str(vault)!r})."
        )
    return path


def _seed_clean_vault(vault: Path) -> None:
    vault.mkdir(parents=True, exist_ok=False)
    for rel in TARGET_TREE:
        (vault / rel).mkdir(parents=True, exist_ok=True)
    for rel, body in _READMES.items():
        target = vault if rel == "." else vault / rel
        (target / "README.md").write_text(body, encoding="utf-8")


def _copy_safe_obsidian_settings(quarantine: Path, vault: Path) -> list[str]:
    src = quarantine / ".obsidian"
    if not src.is_dir():
        return []
    import shutil
    dst = vault / ".obsidian"
    dst.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in sorted(_SAFE_OBSIDIAN_SETTINGS):
        candidate = src / name
        if candidate.is_file():
            shutil.copy2(candidate, dst / name)
            copied.append(name)
    return copied


def do_dry_run(vault: Path, evidence_dir: Path, session_id: str, *, full_manifest: bool) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    summary = _summary_manifest(vault)
    summary_path = _summary_manifest_path(evidence_dir, session_id)
    summary_path.write_text(
        json.dumps({
            "manifest_type": "summary", "vault_path": str(vault),
            "vault_path_sha256": _path_sha(vault), "session_id": session_id,
            "generated_at": _now_iso(), "entries": summary,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result: dict[str, Any] = {
        "mode": "dry_run", "vault_path": str(vault), "session_id": session_id,
        "summary_manifest": str(summary_path), "top_level_entries": len(summary),
        "planned_quarantine_path": str(_quarantine_path(vault, session_id)),
        "planned_target_tree": list(TARGET_TREE),
        "full_manifest": None, "full_manifest_file_count": None,
        "external_roots_touched": False,
    }
    if full_manifest:
        full_path, count = _write_full_manifest(vault, evidence_dir, session_id)
        result["full_manifest"] = str(full_path)
        result["full_manifest_file_count"] = count
    return result


def do_apply(vault: Path, evidence_dir: Path, session_id: str, *,
             copy_safe_obsidian_settings: bool) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    _verify_full_manifest_for_apply(vault, evidence_dir, session_id)
    if not vault.is_dir():
        raise ResetError(f"Vault path does not exist or is not a directory: {vault}")
    quarantine = _quarantine_path(vault, session_id)
    if quarantine.exists():
        raise ResetError(f"Quarantine path already exists: {quarantine}")

    os.rename(vault, quarantine)            # quarantine-first: never delete as a first move
    _seed_clean_vault(vault)
    copied_settings: list[str] = []
    if copy_safe_obsidian_settings:
        copied_settings = _copy_safe_obsidian_settings(quarantine, vault)

    receipt = {
        "mode": "apply", "vault_path": str(vault), "quarantine_path": str(quarantine),
        "session_id": session_id, "applied_at": _now_iso(),
        "target_tree": list(TARGET_TREE), "copied_obsidian_settings": copied_settings,
        "external_roots_touched": False,
        "rollback": [
            "Stop the backend.",
            f'Remove the new vault: rm -rf "{vault}"  (only if you have not added content yet)',
            f'Restore the old vault: mv "{quarantine}" "{vault}"',
        ],
    }
    receipt_evidence = evidence_dir / f"vault-reset-receipt-{session_id}.json"
    receipt_text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    receipt_evidence.write_text(receipt_text, encoding="utf-8")
    (vault / "99 System" / "Receipts" / f"reset-receipt-{session_id}.json").write_text(
        receipt_text, encoding="utf-8"
    )
    receipt["receipt_path"] = str(receipt_evidence)
    return receipt


def do_delete_quarantine(confirm_path: str, evidence_dir: Path, session_id: str) -> dict[str, Any]:
    if not confirm_path:
        raise ResetError("--delete-quarantine requires --confirm-path \"<exact quarantine path>\".")
    target = Path(confirm_path)
    resolved = str(target)
    if resolved in _UNSAFE_EXACT or resolved.rstrip("/") in _UNSAFE_EXACT:
        raise ResetError(f"Refusing unsafe deletion path: {resolved!r}")
    if " - QUARANTINED - " not in target.name:
        raise ResetError(
            f"Refusing to delete a non-quarantine path: {resolved!r} "
            "(name must contain ' - QUARANTINED - ')."
        )
    if not target.is_dir():
        raise ResetError(f"Quarantine path does not exist: {resolved}")
    import shutil
    shutil.rmtree(target)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    receipt = {
        "mode": "delete_quarantine", "deleted_path": resolved, "session_id": session_id,
        "deleted_at": _now_iso(),
    }
    out = evidence_dir / f"vault-reset-deletion-receipt-{session_id}.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt["receipt_path"] = str(out)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Quarantine-first Obsidian vault reset (dry-run by default).")
    parser.add_argument("--vault-path", default=DEFAULT_VAULT_PATH)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--session-id", default=None, help="Reset session id (default: UTC stamp).")
    parser.add_argument("--apply", action="store_true", help="Quarantine + recreate the vault.")
    parser.add_argument("--full-manifest", action="store_true",
                        help="Also write the full recursive manifest (required before --apply).")
    parser.add_argument("--copy-safe-obsidian-settings", action="store_true")
    parser.add_argument("--allow-nonstandard-vault-path", action="store_true",
                        help="Permit a non-default vault path (tests / explicit operator use).")
    parser.add_argument("--allow-running-backend", action="store_true",
                        help="Permit a DRY-RUN while a backend listens on 8000 (never for --apply).")
    parser.add_argument("--delete-quarantine", action="store_true")
    parser.add_argument("--confirm-path", default="")
    args = parser.parse_args(argv)

    session_id = args.session_id or _session_stamp()
    evidence_dir = Path(args.evidence_dir)

    try:
        if args.delete_quarantine:
            result = do_delete_quarantine(args.confirm_path, evidence_dir, session_id)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0

        vault = Path(args.vault_path)
        _validate_vault_path(vault, allow_nonstandard=args.allow_nonstandard_vault_path)

        backend_up = _backend_listening()
        if backend_up and args.apply:
            raise ResetError("Refusing --apply while a backend is listening on port 8000.")
        if backend_up and not args.apply and not args.allow_running_backend:
            raise ResetError(
                "A backend is listening on port 8000. Re-run the dry-run with "
                "--allow-running-backend to preview anyway (apply still refuses)."
            )

        if args.apply:
            result = do_apply(vault, evidence_dir, session_id,
                              copy_safe_obsidian_settings=args.copy_safe_obsidian_settings)
        else:
            result = do_dry_run(vault, evidence_dir, session_id, full_manifest=args.full_manifest)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except ResetError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2, sort_keys=True),
              file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
