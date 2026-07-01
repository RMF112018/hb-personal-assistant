#!/usr/bin/env python3
"""Bounded project-corpus indexer (Phase 10D): index ≤N files from ONE allowlisted project folder,
generate deterministic source cards, and enrich them with the canonical Procore project identity.

Reads ONLY the explicit ``--source-root`` (must be the allowlisted project folder and resolve UNDER a
configured external root so the path-derived project number is retained). Deterministic — NO Ollama, NO
queue/watcher, NO scan outside the root, NO runtime-JSON mutation, NO DB-project-row mutation. This
DOES create source rows + generated cards (the authorized, bounded, count-proven growth). Default is
dry-run; ``--apply`` requires exact confirm flags + a rollback bundle.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import sqlite3
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import obsidian_source_first_indexing_dryrun as dryrun  # noqa: E402

from hb_assistant.obsidian_mcp import source_project_identity as spi  # noqa: E402
from hb_assistant.obsidian_mcp.mutations import create_note, sha256_file  # noqa: E402
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository  # noqa: E402
from hb_assistant.obsidian_mcp.source_indexer import index_source_file  # noqa: E402
from hb_assistant.obsidian_mcp.source_notes import (  # noqa: E402
    _card_rel_path,
    generate_source_card,
)
from hb_assistant.obsidian_mcp.source_value import classify_source_value  # noqa: E402
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError  # noqa: E402

BACKEND_PORT = 8000
_FROZEN_FLAGS = ("external_source_watch_enabled", "source_card_auto_generate_enabled",
                 "source_summary_auto_generate_enabled", "source_note_auto_refresh_enabled")
_SKIP_SUFFIX = (".tmp", ".lock", ".ds_store", ".ini")
# Real project-document extensions only (excludes code/data/archive/image artifacts).
_DOC_EXTS = frozenset({
    ".pdf", ".doc", ".docx", ".rtf", ".txt", ".md", ".xls", ".xlsx", ".xlsm", ".xlsb", ".csv",
    ".ods", ".ppt", ".pptx", ".eml", ".msg", ".xer", ".mpp", ".mpx", ".mpt", ".dwg", ".dxf",
    ".dwf", ".rvt", ".vsdx",
})
_MAX_WALK = 16000


class CorpusError(Exception):
    """Refusal — exit code 3."""


def _backend_listening(port: int = BACKEND_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _queue_counts(db: str) -> tuple[int, int]:
    c = sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)
    try:
        r = c.execute("SELECT COALESCE(SUM(status='queued'),0),COALESCE(SUM(status='processing'),0) "
                      "FROM source_intelligence_events").fetchone()
    finally:
        c.close()
    return int(r[0] or 0), int(r[1] or 0)


def _generated_counts(db: str) -> dict[str, int]:
    c = sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)
    try:
        return {str(k): int(v) for k, v in c.execute(
            "SELECT generation_status,COUNT(*) FROM source_intelligence_generated_notes "
            "GROUP BY generation_status").fetchall()}
    finally:
        c.close()


def _readability(abs_path: Path) -> str:
    try:
        st = abs_path.lstat()
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "read_error"
    if st.st_size > 0 and getattr(st, "st_blocks", 1) == 0:
        return "online_only_or_dataless"
    return "readable"


def _is_temp(name: str) -> bool:
    low = name.lower()
    return name.startswith(("~$", ".")) or low.endswith(_SKIP_SUFFIX) or low == "icon\r"


def _select_corpus(root: Path, *, max_files: int) -> dict[str, Any]:
    """Deterministic, stratified selection of readable project-document files under ``root`` only."""
    seen = evicted = skipped_temp = skipped_nondoc = walked = 0
    by_ext: dict[str, list[Path]] = {}
    for p in sorted(root.rglob("*"), key=lambda x: str(x)):
        if walked >= _MAX_WALK:
            break
        if p.is_dir():
            continue
        walked += 1
        if _is_temp(p.name):
            skipped_temp += 1
            continue
        if p.suffix.lower() not in _DOC_EXTS:
            skipped_nondoc += 1
            continue
        status = _readability(p)
        if status != "readable":
            evicted += 1
            continue
        seen += 1
        by_ext.setdefault(p.suffix.lower() or "(none)", []).append(p)
    # round-robin across extensions for a stratified sample
    selected: list[Path] = []
    queues = [list(v) for v in by_ext.values()]
    while len(selected) < max_files and any(queues):
        for q in queues:
            if q:
                selected.append(q.pop(0))
                if len(selected) >= max_files:
                    break
    selected.sort(key=lambda x: str(x))
    return {"readable_seen": seen, "cloud_evicted": evicted, "skipped_temp": skipped_temp,
            "skipped_nondoc": skipped_nondoc, "selected": selected}


def _folder_bucket(rel: str) -> str:
    """The subfolder immediately under the `NN-NNN-NN - Name` project folder (else '(root)')."""
    parts = [p for p in rel.replace("\\", "/").split("/") if p]
    for i, p in enumerate(parts):
        if re.match(r"^\d{2}-\d{3}-\d{2}\s*-", p):
            return parts[i + 1] if i + 1 < len(parts) - 1 else "(root)"
    return "(root)"


def _resolve_identity(source_root: Path, db_path: str, args: argparse.Namespace) -> spi.ProjectIdentity:
    parsed = spi.parse_project_folder(str(source_root))
    if not parsed:
        raise CorpusError("source root does not match a NN-NNN-NN project folder")
    try:
        ident = spi.resolve_project(number=parsed["project_number"], name=parsed["short_name"],
                                    db_path=db_path)
    except spi.ProjectResolveError as exc:
        raise CorpusError(f"project_resolve: {exc}") from None
    if ident.project_number != args.confirm_project_number or ident.project_key != args.confirm_project_key:
        raise CorpusError(
            f"resolved identity {ident.project_number}/{ident.project_key} != confirmed "
            f"{args.confirm_project_number}/{args.confirm_project_key}")
    return ident


def run(args: argparse.Namespace) -> dict[str, Any]:
    vault_root = Path(args.vault_path).resolve()
    config = dryrun._load_config(args.config_path)
    if Path(str(config.vault_root or "")).resolve() != vault_root:
        raise CorpusError("config vault_root does not match --vault-path")
    source_root = Path(args.source_root).resolve()
    # --confirm-source-root is an apply-time gate; also enforced if explicitly supplied in dry-run.
    if (args.apply or args.confirm_source_root) and \
            str(source_root) != str(Path(args.confirm_source_root).resolve()):
        raise CorpusError("--source-root does not match --confirm-source-root")
    if not source_root.is_dir():
        raise CorpusError("source root is not a directory")
    root_obj = next((r for r in config.external_sources if r.source_root_key == args.root_key), None)
    if root_obj is None:
        raise CorpusError(f"root-key {args.root_key} not in config external_sources")
    base = Path(root_obj.path).resolve()
    if not (source_root == base or base in source_root.parents):
        raise CorpusError("source root is not under the configured external root")

    ident = _resolve_identity(source_root, args.db_path, args)
    repo = SourceIndexRepository(args.db_path)
    sel = _select_corpus(source_root, max_files=args.max_files)
    selected = sel["selected"]

    by_ext: dict[str, int] = {}
    by_bucket: dict[str, int] = {}
    for p in selected:
        rel = str(p.resolve().relative_to(base))
        by_ext[p.suffix.lower() or "(none)"] = by_ext.get(p.suffix.lower() or "(none)", 0) + 1
        by_bucket[_folder_bucket(rel)] = by_bucket.get(_folder_bucket(rel), 0) + 1

    result: dict[str, Any] = {
        "mode": "apply" if args.apply else "dry-run",
        "source_root_confirmed": True,
        "project_number": ident.project_number, "project_key": ident.project_key,
        "procore_project_id": ident.procore_project_id,
        "project_match_basis": list(ident.match_basis),
        "files_readable_seen": sel["readable_seen"], "cloud_evicted": sel["cloud_evicted"],
        "skipped_temp": sel["skipped_temp"], "skipped_nondoc": sel["skipped_nondoc"],
        "files_selected": len(selected),
        "by_extension": dict(sorted(by_ext.items())), "by_folder_bucket": dict(sorted(by_bucket.items())),
        "files_indexed_new": 0, "already_indexed": 0, "cards_generated": 0,
        "cards_skipped_existing": 0, "cards_enriched_existing": 0, "metadata_only": 0,
        "project_number_derived": 0, "skipped_unavailable": 0,
        "queue_delta": 0, "ollama_calls": 0,
        "generated_before": _generated_counts(args.db_path),
    }
    detail_rows: list[dict[str, Any]] = []

    if not args.apply:
        return {"safe": result, "detail_rows": detail_rows, "identity": ident}

    # ---- APPLY gates + rollback bundle (amendment #5) ------------------------------------------
    if not (args.confirm_db_path == args.db_path and args.confirm_vault_path == args.vault_path):
        raise CorpusError("--apply requires matching --confirm-db-path/--confirm-vault-path")
    if any(getattr(config, f, False) for f in _FROZEN_FLAGS):
        raise CorpusError("runtime frozen flags are not all false")
    if _backend_listening():
        raise CorpusError("backend listening on port 8000")
    q0, p0 = _queue_counts(args.db_path)
    if args.require_empty_queue and (q0 or p0):
        raise CorpusError(f"queue not empty (queued={q0}, processing={p0})")
    if not args.backup_dir:
        raise CorpusError("no rollback bundle: --backup-dir required for apply")
    backup_root = Path(args.backup_dir)
    backup_root.mkdir(parents=True, exist_ok=True)
    db_backup = backup_root / "db-backup.sqlite"
    shutil.copy2(args.db_path, db_backup)  # rollback: restore DB from here
    work_dir = vault_root / "Source Notes" / "Work"
    before_cards = {p.name for p in work_dir.glob("*.md")} if work_dir.is_dir() else set()
    (backup_root / "rollback-manifest.json").write_text(json.dumps({
        "db_backup": str(db_backup), "work_cards_before": sorted(before_cards),
        "restore": "restore db_backup over the live DB and delete Work cards created after this run",
    }, indent=2), encoding="utf-8")

    for p in selected:
        abs_p = p.resolve()
        rel = str(abs_p.relative_to(base))
        existing = repo.lookup_by_path("external_file", rel)
        if existing and not args.update:
            source_id = str(existing["source_id"])
            result["already_indexed"] += 1
        else:
            source_id = index_source_file(abs_p, root_obj, repo, config)
            if source_id is None:
                result["skipped_unavailable"] += 1
                continue
            result["files_indexed_new"] += 1
        detail = repo.get_source_detail(source_id) or {}
        if detail.get("project_number"):
            result["project_number_derived"] += 1
        try:
            if classify_source_value(detail, config).disposition.value == "metadata_only":
                result["metadata_only"] += 1
        except Exception:
            pass
        card_rel = _card_rel_path(config, detail)
        carded = repo.has_generated_note(source_id)
        if carded and not args.update:
            result["cards_skipped_existing"] += 1
        else:
            try:
                generate_source_card(repo, config, source_id=source_id, overwrite=args.update,
                                     principal_kind="local")
                result["cards_generated"] += 1
            except ObsidianMcpToolError as exc:
                if exc.code == "note_already_exists":
                    result["cards_skipped_existing"] += 1
                else:
                    result["skipped_unavailable"] += 1
                    detail_rows.append({"rel_bucket": _folder_bucket(rel), "skip": exc.code})
                    continue
        if args.enrich:
            _enrich_card(config, vault_root, card_rel, ident, backup_root, result)
        detail_rows.append({"rel_bucket": _folder_bucket(rel),
                            "project_number": detail.get("project_number")})

    q1, p1 = _queue_counts(args.db_path)
    result["queue_after"] = q1
    result["queue_delta"] = q1 - q0
    result["generated_after"] = _generated_counts(args.db_path)
    if (q1 - q0) or (p1 - p0):
        raise CorpusError("queue changed during apply")
    return {"safe": result, "detail_rows": detail_rows, "identity": ident}


def _enrich_card(config: Any, vault_root: Path, card_rel: str, ident: spi.ProjectIdentity,
                 backup_root: Path, result: dict[str, Any]) -> None:
    target = vault_root / card_rel
    if not target.is_file():
        return
    text = target.read_text(encoding="utf-8")
    new_text, _reason = spi.enrich_card_with_project_identity(text, ident)
    if new_text is None or new_text == text:
        return
    bpath = backup_root / "cards" / card_rel
    bpath.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, bpath)
    create_note(config, path=card_rel, content=new_text, overwrite=True, create_parent_dirs=False,
                expected_sha256=sha256_file(target), caller_surface="mcp",
                tool_name="enrich_project_identity", principal_kind="local")
    result["cards_enriched_existing"] += 1


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db-path", required=True)
    p.add_argument("--config-path",
                   default=str(Path.home() / "Library/Application Support/HB Personal Assistant"
                              / "analytics/obsidian_mcp_config.json"))
    p.add_argument("--vault-path", required=True)
    p.add_argument("--source-root", required=True)
    p.add_argument("--root-key", default="syn-work")
    p.add_argument("--max-files", type=int, default=100)
    p.add_argument("--backup-dir", default=None)
    p.add_argument("--evidence-dir", default=None)
    p.add_argument("--json-output", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--enrich", action="store_true")
    p.add_argument("--update", action="store_true")
    p.add_argument("--confirm-source-root", default="")
    p.add_argument("--confirm-project-number", default="")
    p.add_argument("--confirm-project-key", default="")
    p.add_argument("--confirm-vault-path", default="")
    p.add_argument("--confirm-db-path", default="")
    p.add_argument("--require-empty-queue", action="store_true", default=True)
    p.add_argument("--no-require-empty-queue", dest="require_empty_queue", action="store_false")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        out = run(args)
    except CorpusError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2), file=sys.stderr)
        return 3
    safe, detail_rows = out["safe"], out["detail_rows"]
    if args.evidence_dir:
        ev = Path(args.evidence_dir)
        ev.mkdir(parents=True, exist_ok=True)
        mode = safe["mode"]
        (ev / f"corpus-index-{mode}-summary-safe.json").write_text(
            json.dumps(safe, indent=2, sort_keys=True), encoding="utf-8")
        (ev / f"corpus-index-{mode}-detail-local-sensitive.json").write_text(
            json.dumps({"rows": detail_rows}, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(safe, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
