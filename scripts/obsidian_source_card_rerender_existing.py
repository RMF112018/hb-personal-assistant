#!/usr/bin/env python3
"""Controlled in-place re-render of the EXISTING generated source cards (Phase 9 validation).

Re-renders the exact set of already-generated cards for one domain (default ``work``) using the
current renderer, so the Phase 8 renderer/taxonomy can be validated against production-generated
cards WITHOUT any wider indexing.

Hard properties (by construction):
  * Renderer input is the STORED DB metadata only (``get_source_detail`` -> ``text_excerpt`` etc.).
    The external source file is never read; no cloud download is ever triggered. Source-file
    readability is stat-observed and recorded only (``--require-readable-sources`` is an optional
    strict gate, default off).
  * The original ``generated_at`` is preserved; the re-render is reflected via the card's
    ``updated_at`` content field only. The tool performs ZERO DB mutations: it never creates/deletes
    source rows or generated-note rows, never deletes summaries, never writes relationships, never
    enqueues/drains events, never scans, never starts a backend, never calls ``generate_source_card``.
  * Staging-first: render to a staging dir, validate, and only then overwrite the exact existing card
    files in place via the standard SHA-gated ``create_note`` write path (which also backs up + writes
    its own mutation receipt). The tool additionally copies each existing card to ``--backup-dir``.

Default mode is dry-run. ``--apply`` requires ``--confirm-overwrite-existing-cards``.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import obsidian_source_first_indexing_dryrun as dryrun  # noqa: E402  (reuse _load_config)

from hb_assistant.obsidian_mcp.mutations import create_note, sha256_file  # noqa: E402
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository  # noqa: E402
from hb_assistant.obsidian_mcp.source_notes import (  # noqa: E402
    CARD_VERSION,
    _card_rel_path,
    _domain_for,
    _render_card,
)

BACKEND_PORT = 8000
_DOMAIN_FOLDER = {"work": "Work", "home": "Home", "shared": "Shared"}

# The canonical 11-section card body, in exact required order (Phase 8 template contract).
CANONICAL_SECTIONS = [
    "## Source Summary", "## Why This Matters", "## PM Review Cues", "## Key Facts",
    "## Related Project", "## Related People / Companies", "## Related Decisions",
    "## Related Meetings", "## Source Basis", "## Advisory Summary", "## Follow-Up",
]
# Old top-level sections that must NOT appear (type-specific facts belong inside Key Facts).
FORBIDDEN_OLD_SECTIONS = [
    "## Overview", "## Indexed Text Preview", "## Source Reference", "## File Analysis",
    "## Drawing Identity", "## Spreadsheet Identity", "## Spreadsheet Signals",
    "## Bid Package Identity", "## Bid Package Inclusions", "## Bid Package Exclusions",
    "## Document Identity",
]
# Sections whose body must be non-empty.
_REQUIRED_NONEMPTY = [
    "## Source Summary", "## Why This Matters", "## PM Review Cues", "## Key Facts",
    "## Source Basis", "## Advisory Summary", "## Follow-Up",
]
_SUFFIX_RE = re.compile(r"__[A-Za-z0-9_-]{8,}\.md$")


class RerenderError(Exception):
    """Refusal — printed as a controlled error, exit code 3."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _backend_listening(port: int = BACKEND_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _readability_status(abs_path: Path) -> str:
    """Stat-only readability (NO read -> never triggers a cloud download).

    'online_only_or_dataless' for cloud placeholders (size > 0 but 0 allocated blocks),
    'read_error' if it can't be stat'd, 'missing' if absent, else 'readable'.
    """
    try:
        st = abs_path.lstat()
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "read_error"
    if st.st_size > 0 and getattr(st, "st_blocks", 1) == 0:
        return "online_only_or_dataless"
    return "readable"


def _queue_counts(db: str) -> tuple[int, int]:
    """(queued, processing) via a read-only connection — never claims/mutates events."""
    c = sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)
    try:
        row = c.execute(
            "SELECT COALESCE(SUM(status='queued'),0), COALESCE(SUM(status='processing'),0) "
            "FROM source_intelligence_events"
        ).fetchone()
    finally:
        c.close()
    return int(row[0] or 0), int(row[1] or 0)


def _frontmatter_value(text: str, key: str) -> str | None:
    """Read a scalar frontmatter value from the leading --- block (quotes stripped)."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    block = text[:end] if end != -1 else text
    m = re.search(rf"(?m)^{re.escape(key)}:\s*(.*?)\s*$", block)
    if not m:
        return None
    return m.group(1).strip().strip('"') or None


def _section_body(text: str, heading: str) -> list[str]:
    out: list[str] = []
    capturing = False
    for line in text.splitlines():
        if line == heading:
            capturing = True
            continue
        if capturing and line.startswith("## "):
            break
        if capturing and line.strip():
            out.append(line)
    return out


def validate_card(text: str, *, expected_domain: str) -> dict[str, Any]:
    """Structural/quality validation of a rendered card. Returns per-dimension booleans + issues."""
    issues: list[str] = []
    has_fm = text.startswith("---") and "\n---" in text
    if not has_fm:
        issues.append("missing_frontmatter")
    card_version_ok = _frontmatter_value(text, "card_version") == CARD_VERSION
    if not card_version_ok:
        issues.append("wrong_card_version")
    domain_ok = _frontmatter_value(text, "domain") == expected_domain
    if not domain_ok:
        issues.append("wrong_domain")

    headings = [ln for ln in text.splitlines() if ln.startswith("## ")]
    canonical_ok = headings == CANONICAL_SECTIONS
    if not canonical_ok:
        issues.append("section_order_or_set_mismatch")

    old_absent = True
    for old in FORBIDDEN_OLD_SECTIONS:
        if old in text:
            old_absent = False
            issues.append(f"forbidden_old_section:{old}")

    nonempty_ok = True
    for sec in _REQUIRED_NONEMPTY:
        if not _section_body(text, sec):
            nonempty_ok = False
            issues.append(f"empty_section:{sec}")

    no_raw_preview = "Indexed Text Preview" not in text and "> _(truncated preview" not in text
    if not no_raw_preview:
        issues.append("raw_text_preview")

    # No invented relationships: Decisions/Meetings stay the explicit no-link lines; Project/People
    # use detected-not-resolved phrasing; no wikilinks anywhere in the card body.
    decisions = " ".join(_section_body(text, "## Related Decisions"))
    meetings = " ".join(_section_body(text, "## Related Meetings"))
    project = " ".join(_section_body(text, "## Related Project"))
    people = " ".join(_section_body(text, "## Related People / Companies"))
    rel_ok = (
        "No related decisions linked yet." in decisions
        and "No related meetings linked yet." in meetings
        and ("no project record linked yet" in project or "No project number detected" in project)
        and ("no company record linked yet" in people
             or "No people or companies detected" in people)
        and "[[" not in text
    )
    if not rel_ok:
        issues.append("invented_relationship")

    # Exactly one hb-local-summary block (the qwen2.5:14b append target).
    block_ok = (text.count("hb-local-summary:start") == 1
                and text.count("hb-local-summary:end") == 1)
    if not block_ok:
        issues.append("local_summary_block")

    return {
        "frontmatter": has_fm,
        "card_version": card_version_ok,
        "domain": domain_ok,
        "canonical_sections": canonical_ok,
        "old_sections_absent": old_absent,
        "required_sections_nonempty": nonempty_ok,
        "no_raw_preview": no_raw_preview,
        "no_invented_relationship": rel_ok,
        "local_summary_block": block_ok,
        "passed": not issues,
        "issues": issues,
    }


def _aggregate_validation(per_card: list[dict[str, Any]]) -> dict[str, Any]:
    dims = ["frontmatter", "card_version", "domain", "canonical_sections", "old_sections_absent",
            "required_sections_nonempty", "no_raw_preview", "no_invented_relationship",
            "local_summary_block", "passed"]
    out: dict[str, Any] = {"total": len(per_card)}
    for d in dims:
        passed = sum(1 for c in per_card if c.get(d))
        out[d] = {"pass": passed, "fail": len(per_card) - passed}
    return out


def _select_existing(repo: SourceIndexRepository, domain_folder: str,
                     expected_count: int) -> list[dict[str, Any]]:
    """The existing generated cards routed under Source Notes/<domain_folder>/. Fail-closed."""
    # Select every routed card row (generated + stale) so a non-'generated' row is caught by the
    # per-row guard below rather than silently skipped.
    prefix = f"Source Notes/{domain_folder}/"
    rows = [r for r in repo.list_generated_notes(statuses=("generated", "stale"))
            if str(r.get("note_rel_path") or "").startswith(prefix)]
    rows.sort(key=lambda r: str(r["note_rel_path"]))
    if len(rows) != expected_count:
        raise RerenderError(
            f"selected {len(rows)} generated cards under {prefix} but expected {expected_count}")
    return rows


def run(args: argparse.Namespace, *, now_iso_fn: Callable[[], str] = _now_iso) -> dict[str, Any]:
    domain = args.domain
    if domain not in _DOMAIN_FOLDER:
        raise RerenderError(f"unsupported domain: {domain}")
    domain_folder = _DOMAIN_FOLDER[domain]
    vault_root = Path(args.vault_path).resolve()

    config = dryrun._load_config(args.config_path)
    cfg_vault = Path(str(config.vault_root)).resolve() if config.vault_root else None
    if cfg_vault != vault_root:
        raise RerenderError(
            f"config vault_root does not match --vault-path ({cfg_vault} != {vault_root})")

    repo = SourceIndexRepository(args.db_path)
    rows = _select_existing(repo, domain_folder, args.expected_count)

    staging_root = Path(args.staging_dir)
    rerender_at = now_iso_fn()
    detail_rows: list[dict[str, Any]] = []
    plans: list[dict[str, Any]] = []  # in-memory render plan (content reused for apply)
    per_card_validation: list[dict[str, Any]] = []
    readability_counts = {"readable": 0, "online_only_or_dataless": 0, "read_error": 0, "missing": 0}

    for row in rows:
        source_id = str(row["source_id"])
        note_rel = str(row["note_rel_path"])
        if row.get("generation_status") != "generated":
            raise RerenderError(f"generated-note row is not 'generated' (source {source_id[:12]})")
        if ".." in note_rel or not note_rel.startswith(f"Source Notes/{domain_folder}/"):
            raise RerenderError(f"target path outside Source Notes/{domain_folder}/")
        if not _SUFFIX_RE.search(Path(note_rel).name):
            raise RerenderError("target filename does not match the generated-card suffix pattern")

        detail = repo.get_source_detail(source_id)
        if detail is None:
            raise RerenderError(f"missing source record for generated card (source {source_id[:12]})")

        card_rel = _card_rel_path(config, detail)
        if card_rel != note_rel:
            raise RerenderError("recomputed card path differs from the recorded note path")
        if _domain_for(detail) != domain:
            raise RerenderError(f"source does not route to domain {domain}")

        target = vault_root / note_rel
        if not target.is_file():
            raise RerenderError("existing target card file is missing")
        existing_text = target.read_text(encoding="utf-8")

        # Source-file readability is OBSERVED ONLY (render is DB-only; no file read).
        readability = "n/a"
        if detail.get("rel_path") and detail.get("source_root_key"):
            root = next((r for r in config.external_sources
                         if r.source_root_key == detail["source_root_key"]), None)
            if root is not None:
                readability = _readability_status(Path(root.path) / str(detail["rel_path"]))
                readability_counts[readability] = readability_counts.get(readability, 0) + 1
                if args.require_readable_sources and readability != "readable":
                    raise RerenderError(
                        f"source not readable ({readability}) and --require-readable-sources set")

        # Preserve the original generation timestamp; reflect the re-render via updated_at content only.
        original_generated_at = _frontmatter_value(existing_text, "generated_at") or rerender_at
        render_detail = dict(detail)
        render_detail["updated_at"] = rerender_at
        content = _render_card(config, render_detail, original_generated_at, repo=repo)

        staged_path = staging_root / note_rel
        staged_path.parent.mkdir(parents=True, exist_ok=True)
        staged_path.write_text(content, encoding="utf-8")

        validation = validate_card(content, expected_domain=domain)
        per_card_validation.append(validation)
        plans.append({"source_id": source_id, "note_rel": note_rel, "content": content,
                      "existing_text": existing_text, "target": target,
                      "original_generated_at": original_generated_at})
        detail_rows.append({"source_id12": source_id[:12], "note_rel_path": note_rel,
                            "readability": readability, "validation_passed": validation["passed"],
                            "issues": validation["issues"]})

    staged_count = len(plans)
    if staged_count != args.expected_count:
        raise RerenderError(f"staged {staged_count} cards but expected {args.expected_count}")
    validation_summary = _aggregate_validation(per_card_validation)
    staging_valid = validation_summary["passed"]["fail"] == 0

    result: dict[str, Any] = {
        "mode": "apply" if args.apply else "dry-run",
        "domain": domain,
        "renderer_input_source": "stored_db_metadata",
        "external_source_files_read": 0,
        "cloud_download_triggered": False,
        "source_readability_observed_only": True,
        "expected_count": args.expected_count,
        "selected_existing_cards": len(rows),
        "target_files_found": staged_count,
        "source_records_found": staged_count,
        "staged_cards_rendered": staged_count,
        "source_readability_counts": readability_counts,
        "require_readable_sources": bool(args.require_readable_sources),
        "staging_validation": validation_summary,
        "staging_validation_passed": staging_valid,
        "generated_at_preserved": True,
        "rerender_updated_at": rerender_at,
    }

    if not staging_valid:
        raise RerenderError(
            f"staging validation failed for {validation_summary['passed']['fail']} card(s)")

    if not args.apply:
        result.update({"backed_up_cards": 0, "overwritten_cards": 0, "created_cards": 0,
                       "deleted_cards": 0, "queue_delta": 0, "summaries_generated": 0,
                       "source_scans": 0, "backend_starts": 0, "db_mutations": _zero_db_mutations(),
                       "create_note_receipts": 0})
        return {"safe": result, "detail_rows": detail_rows}

    # ---- APPLY ----------------------------------------------------------------------------------
    if args.confirm_overwrite_existing_cards is not True:
        raise RerenderError("--apply requires --confirm-overwrite-existing-cards")
    if _backend_listening():
        raise RerenderError("backend is listening on port 8000; refusing to write")
    q0, p0 = _queue_counts(args.db_path)
    if q0 != 0 or p0 != 0:
        raise RerenderError(f"queue not empty before apply (queued={q0}, processing={p0})")

    backup_root = Path(args.backup_dir)
    backed_up = overwritten = created = deleted = receipts = 0
    for plan in plans:
        target: Path = plan["target"]
        if not target.is_file():  # disappeared between staging and apply
            raise RerenderError("apply would create a new card (target no longer exists)")
        # Explicit backup (in addition to create_note's own backup).
        backup_path = backup_root / plan["note_rel"]
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup_path)
        backed_up += 1
        expected_sha = sha256_file(target)
        out = create_note(
            config, path=plan["note_rel"], content=plan["content"], overwrite=True,
            create_parent_dirs=False, expected_sha256=expected_sha, caller_surface="mcp",
            tool_name="rerender_existing_source_card", principal_kind="local",
        )
        receipts += 1  # create_note always appends one mutation receipt
        if out.get("created"):
            created += 1
        if out.get("overwritten"):
            overwritten += 1
        if not target.is_file():
            raise RerenderError("apply deleted a target card (unexpected)")
    if created != 0:
        raise RerenderError(f"apply created {created} new cards (expected 0)")
    q1, p1 = _queue_counts(args.db_path)
    if (q1 - q0) != 0 or (p1 - p0) != 0:
        raise RerenderError(f"queue changed during apply (delta queued={q1 - q0}, proc={p1 - p0})")

    result.update({
        "backed_up_cards": backed_up, "overwritten_cards": overwritten, "created_cards": created,
        "deleted_cards": deleted, "queue_before": q0, "queue_after": q1, "queue_delta": q1 - q0,
        "summaries_generated": 0, "source_scans": 0, "backend_starts": 0,
        "create_note_receipts": receipts, "db_mutations": _zero_db_mutations(),
    })
    return {"safe": result, "detail_rows": detail_rows}


def _zero_db_mutations() -> dict[str, int]:
    """This tool performs zero DB mutations (generated_at preserved; nothing written)."""
    return {"generated_note_rows_created": 0, "generated_note_rows_refreshed": 0,
            "source_rows_written": 0, "summaries_deleted": 0, "relationships_written": 0,
            "events_enqueued": 0}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db-path", required=True)
    p.add_argument("--vault-path", required=True)
    p.add_argument("--domain", default="work", choices=sorted(_DOMAIN_FOLDER))
    p.add_argument("--expected-count", type=int, required=True)
    p.add_argument("--backup-dir", required=True)
    p.add_argument("--staging-dir", required=True)
    p.add_argument("--evidence-dir", default=None)
    p.add_argument("--config-path",
                   default=str(Path.home() / "Library/Application Support/HB Personal Assistant"
                              / "analytics/obsidian_mcp_config.json"))
    p.add_argument("--require-readable-sources", action="store_true")
    p.add_argument("--json-output", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--confirm-overwrite-existing-cards", action="store_true")
    return p


def main(argv: list[str] | None = None, *, now_iso_fn: Callable[[], str] = _now_iso) -> int:
    args = _build_parser().parse_args(argv)
    try:
        out = run(args, now_iso_fn=now_iso_fn)
    except RerenderError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2), file=sys.stderr)
        return 3
    safe, detail_rows = out["safe"], out["detail_rows"]
    if args.evidence_dir:
        ev = Path(args.evidence_dir)
        ev.mkdir(parents=True, exist_ok=True)
        mode = safe["mode"]
        (ev / f"rerender-{args.domain}-{mode}-summary-safe.json").write_text(
            json.dumps(safe, indent=2, sort_keys=True), encoding="utf-8")
        (ev / f"rerender-{args.domain}-{mode}-detail-local-sensitive.json").write_text(
            json.dumps({"rows": detail_rows}, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(safe, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
