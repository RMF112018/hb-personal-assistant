#!/usr/bin/env python3
"""Bounded `.eml` email-archive indexer (Phase 10E): parse ≤N saved emails from ONE allowlisted project
folder into full-fidelity Markdown archive notes + first-class email source cards, then feed graph-safe
email facts into the note graph.

Reads ONLY the explicit ``--source-root`` (must be the allowlisted project folder and resolve UNDER a
configured external root so the path-derived project number is retained). Deterministic — NO Ollama, NO
queue/watcher, NO scan outside the root, NO runtime-JSON mutation, NO DB-project-row mutation. Archive
notes are vault files (NOT DB-tracked generated cards); source cards are the concise graph/index cards.
Default is dry-run; ``--apply`` requires exact confirm flags + a rollback bundle. ``--update`` upgrades
existing (e.g. Phase 10D) `.eml` cards in place — never creating a duplicate card for the same file.
"""

from __future__ import annotations

import argparse
import json
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

from hb_assistant.obsidian_mcp import source_archive_paths as sap  # noqa: E402
from hb_assistant.obsidian_mcp import source_email_archive as sea  # noqa: E402
from hb_assistant.obsidian_mcp import source_project_identity as spi  # noqa: E402
from hb_assistant.obsidian_mcp import source_subroot as ss  # noqa: E402
from hb_assistant.obsidian_mcp.mutations import create_note, sha256_file  # noqa: E402
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository  # noqa: E402
from hb_assistant.obsidian_mcp.source_indexer import (  # noqa: E402
    EMAIL_ARCHIVE_FOLDER,
    index_source_file,
)
from hb_assistant.obsidian_mcp.source_notes import (  # noqa: E402
    _card_rel_path,
    generate_source_card,
)
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError  # noqa: E402

BACKEND_PORT = 8000
_FROZEN_FLAGS = ("external_source_watch_enabled", "source_card_auto_generate_enabled",
                 "source_summary_auto_generate_enabled", "source_note_auto_refresh_enabled")
_SKIP_SUFFIX = (".tmp", ".lock", ".ds_store", ".ini")
_EML_EXTS = frozenset({".eml"})
_MAX_WALK = 16000


class EmlArchiveError(Exception):
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


def _select_eml(root: Path, *, max_files: int,
                include_subroots: list[Path] | None = None) -> dict[str, Any]:
    """Deterministic selection of readable `.eml` files under ``root`` only (bounded).

    When ``include_subroots`` is given, traversal starts AT each bounded subroot (symlink-safe,
    containment-checked) instead of the project root.
    """
    seen = evicted = skipped_temp = skipped_nondoc = walked = 0
    inc_listable = inc_failed = inc_containment_rejected = 0
    found: list[Path] = []
    if include_subroots is not None:
        candidates: list[Path] = []
        for base in include_subroots:
            if base.is_symlink():
                inc_failed += 1
                continue
            files, st = ss.walk_files(base, root, max_files=_MAX_WALK)
            inc_listable += 1 if st["listable"] else 0
            inc_failed += 0 if st["listable"] else 1
            inc_containment_rejected += st["containment_rejected"]
            candidates.extend(files)
        walk_iter: list[Path] = sorted(set(candidates), key=str)
    else:
        walk_iter = sorted(root.rglob("*"), key=lambda x: str(x))
    for p in walk_iter:
        if walked >= _MAX_WALK:
            break
        if p.is_dir():
            continue
        walked += 1
        if _is_temp(p.name):
            skipped_temp += 1
            continue
        if p.suffix.lower() not in _EML_EXTS:
            skipped_nondoc += 1
            continue
        if _readability(p) != "readable":
            evicted += 1
            continue
        seen += 1
        found.append(p)
    selected = found[:max_files]
    return {"readable_seen": seen, "cloud_evicted": evicted, "skipped_temp": skipped_temp,
            "skipped_nondoc": skipped_nondoc, "selected": selected,
            "include_subroots_listable": inc_listable, "include_subroots_failed": inc_failed,
            "include_subroots_containment_rejected": inc_containment_rejected}


def _folder_bucket(rel: str) -> str:
    """The subfolder immediately under the `NN-NNN-NN - Name` project folder (else '(root)')."""
    import re
    parts = [p for p in rel.replace("\\", "/").split("/") if p]
    for i, p in enumerate(parts):
        if re.match(r"^\d{2}-\d{3}-\d{2}\s*-", p):
            return parts[i + 1] if i + 1 < len(parts) - 1 else "(root)"
    return "(root)"


def _resolve_identity(source_root: Path, db_path: str, args: argparse.Namespace) -> spi.ProjectIdentity:
    parsed = spi.parse_project_folder(str(source_root))
    if not parsed:
        raise EmlArchiveError("source root does not match a NN-NNN-NN project folder")
    try:
        ident = spi.resolve_project(number=parsed["project_number"], name=parsed["short_name"],
                                    db_path=db_path)
    except spi.ProjectResolveError as exc:
        raise EmlArchiveError(f"project_resolve: {exc}") from None
    if ident.project_number != args.confirm_project_number or ident.project_key != args.confirm_project_key:
        raise EmlArchiveError(
            f"resolved identity {ident.project_number}/{ident.project_key} != confirmed "
            f"{args.confirm_project_number}/{args.confirm_project_key}")
    return ident


def _archive_rel_path(detail: dict[str, Any]) -> str:
    """Full-email archive note path: ``Email Archive/<Domain>/<safe>__<id12>.md`` (Phase 10L-B).

    Delegates to the centralized :func:`source_archive_paths.archive_note_rel_path` — the single source
    of truth for archive routing. Routes DIRECTLY under the domain folder (Phase 10L-B corrected the
    pre-10L double-domain ``Email Archive/Work/<Domain>/`` layout). Lives in a SEPARATE top-level
    ``Email Archive`` root (NOT under Source Notes), so it is never a source-card path
    (``_card_rel_path`` never produces this) and never a generated note. Self-index protection comes
    from ``is_email_archive_path`` (keyed on the ``Email Archive/`` prefix), which excludes it from
    ``scan_vault_notes``/the watcher so full bodies/addresses never reach the FTS.
    """
    return sap.archive_note_rel_path(detail)


def run(args: argparse.Namespace) -> dict[str, Any]:
    vault_root = Path(args.vault_path).resolve()
    config = dryrun._load_config(args.config_path)
    if Path(str(config.vault_root or "")).resolve() != vault_root:
        raise EmlArchiveError("config vault_root does not match --vault-path")
    source_root = Path(args.source_root).resolve()
    if (args.apply or args.confirm_source_root) and \
            str(source_root) != str(Path(args.confirm_source_root).resolve()):
        raise EmlArchiveError("--source-root does not match --confirm-source-root")
    if not source_root.is_dir():
        raise EmlArchiveError("source root is not a directory")
    root_obj = next((r for r in config.external_sources if r.source_root_key == args.root_key), None)
    if root_obj is None:
        raise EmlArchiveError(f"root-key {args.root_key} not in config external_sources")
    base = Path(root_obj.path).resolve()
    if not (source_root == base or base in source_root.parents):
        raise EmlArchiveError("source root is not under the configured external root")

    try:
        subroots = [ss.validate_subroot(source_root, s) for s in (args.include_subroot or [])]
    except ss.SubrootError as exc:
        raise EmlArchiveError(f"invalid --include-subroot: {exc}") from None

    ident = _resolve_identity(source_root, args.db_path, args)
    repo = SourceIndexRepository(args.db_path)
    sel = _select_eml(source_root, max_files=args.max_eml, include_subroots=subroots or None)
    selected = sel["selected"]

    by_bucket: dict[str, int] = {}
    for p in selected:
        rel = str(p.resolve().relative_to(base))
        by_bucket[_folder_bucket(rel)] = by_bucket.get(_folder_bucket(rel), 0) + 1

    result: dict[str, Any] = {
        "mode": "apply" if args.apply else "dry-run",
        "source_root_confirmed": True,
        "project_number": ident.project_number, "project_key": ident.project_key,
        "procore_project_id": ident.procore_project_id,
        "project_match_basis": list(ident.match_basis),
        "include_subroots_requested": len(subroots),
        "include_subroots_listable": sel["include_subroots_listable"],
        "include_subroots_failed": sel["include_subroots_failed"],
        "include_subroots_containment_rejected": sel["include_subroots_containment_rejected"],
        "eml_found": sel["readable_seen"], "cloud_evicted": sel["cloud_evicted"],
        "skipped_temp": sel["skipped_temp"], "skipped_non_eml": sel["skipped_nondoc"],
        "eml_selected": len(selected), "by_folder_bucket": dict(sorted(by_bucket.items())),
        # amendment #1: distinct accounting — archive notes are vault files, NOT generated-note rows.
        "eml_parsed": 0, "eml_parse_failed": 0,
        "emails_with_attachments": 0, "attachments_total": 0,
        "plain_body_present": 0, "html_body_present": 0,
        "source_cards_generated": 0, "source_cards_updated": 0,
        "already_indexed": 0, "skipped_unavailable": 0,
        "archive_notes_created": 0, "archive_notes_updated": 0,
        "graph_facts_written": 0, "project_number_derived": 0,
        "generated_note_delta": 0, "vault_markdown_delta": 0,
        "queue_delta": 0, "ollama_calls": 0,
        "generated_before": _generated_counts(args.db_path),
    }
    detail_rows: list[dict[str, Any]] = []

    if not args.apply:
        return {"safe": result, "detail_rows": detail_rows, "identity": ident}

    # ---- APPLY gates + rollback bundle ---------------------------------------------------------
    if not (args.confirm_db_path == args.db_path and args.confirm_vault_path == args.vault_path):
        raise EmlArchiveError("--apply requires matching --confirm-db-path/--confirm-vault-path")
    if any(getattr(config, f, False) for f in _FROZEN_FLAGS):
        raise EmlArchiveError("runtime frozen flags are not all false")
    if _backend_listening():
        raise EmlArchiveError("backend listening on port 8000")
    q0, p0 = _queue_counts(args.db_path)
    if args.require_empty_queue and (q0 or p0):
        raise EmlArchiveError(f"queue not empty (queued={q0}, processing={p0})")
    if not args.backup_dir:
        raise EmlArchiveError("no rollback bundle: --backup-dir required for apply")
    backup_root = Path(args.backup_dir)
    backup_root.mkdir(parents=True, exist_ok=True)
    db_backup = backup_root / "db-backup.sqlite"
    shutil.copy2(args.db_path, db_backup)  # rollback: restore DB from here
    sn_dir = vault_root / (config.source_notes_folder or "Source Notes").strip("/")
    before_notes = sorted(str(p.relative_to(vault_root)) for p in sn_dir.rglob("*.md")) \
        if sn_dir.is_dir() else []
    ea_dir = vault_root / EMAIL_ARCHIVE_FOLDER
    before_archives = sorted(str(p.relative_to(vault_root)) for p in ea_dir.rglob("*.md")) \
        if ea_dir.is_dir() else []
    (backup_root / "rollback-manifest.json").write_text(json.dumps({
        "db_backup": str(db_backup), "source_notes_md_before": before_notes,
        "email_archive_md_before": before_archives,
        "restore": "restore db_backup over the live DB, delete Source Notes cards created after "
                   "this run, and delete Email Archive/ notes not present in email_archive_md_before",
    }, indent=2), encoding="utf-8")

    for p in selected:
        abs_p = p.resolve()
        rel = str(abs_p.relative_to(base))
        bucket = _folder_bucket(rel)
        existing = repo.lookup_by_path("external_file", rel)
        if existing and not args.update:
            result["already_indexed"] += 1
            detail_rows.append({"rel_bucket": bucket, "skip": "already_indexed"})
            continue
        source_id = index_source_file(abs_p, root_obj, repo, config)
        if source_id is None:
            result["skipped_unavailable"] += 1
            detail_rows.append({"rel_bucket": bucket, "skip": "unavailable"})
            continue

        # Parse the email once for the archive note + graph-safe card facts.
        email = sea.parse_email_file(abs_p)
        if email.parse_status == "failed":
            result["eml_parse_failed"] += 1
            detail_rows.append({"rel_bucket": bucket, "skip": "parse_failed"})
            continue
        result["eml_parsed"] += 1
        true_atts = [a for a in email.attachments if not a.is_inline]
        if true_atts:
            result["emails_with_attachments"] += 1
            result["attachments_total"] += len(true_atts)
        if email.plain_body is not None:
            result["plain_body_present"] += 1
        if email.html_body is not None:
            result["html_body_present"] += 1

        detail = repo.get_source_detail(source_id) or {}
        if detail.get("project_number"):
            result["project_number_derived"] += 1
        facts = sea.email_card_facts(email)

        # 1) Full-fidelity archive note (vault file, NOT a generated-note row).
        archive_rel = _archive_rel_path(detail)
        _write_archive_note(config, vault_root, archive_rel, email, ident,
                            str(detail.get("content_sha256") or ""), backup_root, result)

        # 2) Concise source card (idempotent: same source_id -> same card path; --update overwrites).
        carded = repo.has_generated_note(source_id)
        try:
            generate_source_card(repo, config, source_id=source_id, overwrite=args.update,
                                 principal_kind="local")
            result["source_cards_updated" if carded else "source_cards_generated"] += 1
        except ObsidianMcpToolError as exc:
            if exc.code == "note_already_exists":
                result["source_cards_updated"] += 1
            else:
                result["skipped_unavailable"] += 1
                detail_rows.append({"rel_bucket": bucket, "skip": exc.code})
                continue

        # 3) Enrich the card: canonical project identity (10D) + graph-safe hb-email block (10E).
        card_rel = _card_rel_path(config, detail)
        _enrich_card(config, vault_root, card_rel, ident, email, archive_rel, facts,
                     backup_root, result)
        detail_rows.append({"rel_bucket": bucket, "project_number": detail.get("project_number")})

    q1, p1 = _queue_counts(args.db_path)
    result["queue_after"] = q1
    result["queue_delta"] = q1 - q0
    gen_after = _generated_counts(args.db_path)
    result["generated_after"] = gen_after
    result["generated_note_delta"] = sum(gen_after.values()) - sum(result["generated_before"].values())
    result["vault_markdown_delta"] = result["source_cards_generated"] + result["archive_notes_created"]
    if (q1 - q0) or (p1 - p0):
        raise EmlArchiveError("queue changed during apply")
    return {"safe": result, "detail_rows": detail_rows, "identity": ident}


def _write_archive_note(config: Any, vault_root: Path, archive_rel: str, email: sea.EmailArchive,
                        ident: spi.ProjectIdentity, source_hash: str, backup_root: Path,
                        result: dict[str, Any]) -> None:
    target = vault_root / archive_rel
    existed = target.is_file()
    content = sea.render_email_archive_note(email, ident, source_hash)
    expected = sha256_file(target) if existed else None
    if existed:
        bpath = backup_root / "archives" / archive_rel
        bpath.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, bpath)
    create_note(config, path=archive_rel, content=content, overwrite=existed,
                create_parent_dirs=True, expected_sha256=expected, caller_surface="mcp",
                tool_name="email_archive_note", principal_kind="local")
    result["archive_notes_updated" if existed else "archive_notes_created"] += 1


def _enrich_card(config: Any, vault_root: Path, card_rel: str, ident: spi.ProjectIdentity,
                 email: sea.EmailArchive, archive_rel: str, facts: dict[str, Any],
                 backup_root: Path, result: dict[str, Any]) -> None:
    target = vault_root / card_rel
    if not target.is_file():
        return
    text = target.read_text(encoding="utf-8")
    step1, _r1 = spi.enrich_card_with_project_identity(text, ident)
    working = step1 if step1 is not None else text
    step2, _r2 = sea.enrich_card_with_email(working, email, archive_rel, facts=facts)
    new_text = step2 if step2 is not None else working
    if new_text == text:
        return
    bpath = backup_root / "cards" / card_rel
    bpath.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, bpath)
    create_note(config, path=card_rel, content=new_text, overwrite=True, create_parent_dirs=False,
                expected_sha256=sha256_file(target), caller_surface="mcp",
                tool_name="enrich_email_card", principal_kind="local")
    if step2 is not None:
        result["graph_facts_written"] += 1


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db-path", required=True)
    p.add_argument("--config-path",
                   default=str(Path.home() / "Library/Application Support/HB Personal Assistant"
                              / "analytics/obsidian_mcp_config.json"))
    p.add_argument("--vault-path", required=True)
    p.add_argument("--source-root", required=True)
    p.add_argument("--root-key", default="syn-work")
    p.add_argument("--include-subroot", action="append", default=[],
                   help="bounded relative subroot under --source-root (repeatable); starts traversal "
                        "at the subroot so locally-available descendants are selectable even when the "
                        "project root fails root-level enumeration")
    p.add_argument("--max-eml", type=int, default=10)
    p.add_argument("--backup-dir", default=None)
    p.add_argument("--evidence-dir", default=None)
    p.add_argument("--json-output", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
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
    except EmlArchiveError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2), file=sys.stderr)
        return 3
    safe, detail_rows = out["safe"], out["detail_rows"]
    if args.evidence_dir:
        ev = Path(args.evidence_dir)
        ev.mkdir(parents=True, exist_ok=True)
        mode = safe["mode"]
        (ev / f"eml-archive-{mode}-summary-safe.json").write_text(
            json.dumps(safe, indent=2, sort_keys=True), encoding="utf-8")
        (ev / f"eml-archive-{mode}-detail-local-sensitive.json").write_text(
            json.dumps({"rows": detail_rows}, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(safe, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
