#!/usr/bin/env python3
"""Bounded, single-root FIRST production indexing apply.

Generates real domain-routed source cards for EXACTLY the selected candidates and nothing else, via
the direct path ``index_source_file`` → ``generate_source_card`` (NO event queue: never enqueues,
never drains, never claims unrelated queued events). Selection reuses the Phase-5 dry-run module so it
is identical to the read-only preview. DRY-RUN/preview by default; production writes require ``--apply``
plus exact confirmations and a clean queue / stopped backend.

Hard scope for this first batch: one root (``syn-work``), ``auto_card_high`` + domain ``work`` only,
<= 25 cards, 0 summaries.
"""

from __future__ import annotations

import argparse
import json
import socket
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

# Reuse the dry-run module for IDENTICAL selection logic (walk + classify).
import obsidian_source_first_indexing_dryrun as dryrun  # noqa: E402

BACKEND_PORT = 8000


class ApplyError(Exception):
    """Refusal — printed as a controlled error, exit code 3."""


def _backend_listening(port: int = BACKEND_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _queue_counts(db: str) -> tuple[int, int]:
    c = sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)
    try:
        row = c.execute(
            "SELECT COALESCE(SUM(status='queued'),0), COALESCE(SUM(status='processing'),0) "
            "FROM source_intelligence_events"
        ).fetchone()
    finally:
        c.close()
    return int(row[0] or 0), int(row[1] or 0)


def _select_candidates(config: Any, root_path: Path, root_key: str, *, max_files: int,
                       max_seconds: float, max_candidates: int,
                       now_fn: Callable[[], float]) -> list[dict[str, Any]]:
    """Deterministic, bounded selection: auto_card_high + domain work, sorted by rel_path, capped."""
    scan = dryrun.scan_root(root_path, root_key, config, max_files=max_files,
                            max_seconds=max_seconds, include_hidden=False, now_fn=now_fn)
    rows = [r for r in scan["detail_rows"]
            if r["disposition"] == "auto_card_high" and r["domain"] == "work"]
    rows.sort(key=lambda r: r["rel_path"])
    return rows[:max_candidates]


def run(args: argparse.Namespace, *, now_fn: Callable[[], float]) -> dict[str, Any]:
    from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository
    from hb_assistant.obsidian_mcp.source_indexer import index_source_file
    from hb_assistant.obsidian_mcp.source_notes import (
        _card_rel_path,
        _domain_for,
        generate_source_card,
    )
    from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError

    config = dryrun._load_config(args.config_path)
    # Validate the root (disabled/missing/unmounted/in-vault/quarantine all raise) — reuse dry-run.
    try:
        root_path = dryrun._resolve_root(config, args.root_key, Path(args.vault_path))
    except dryrun.DryRunError as exc:
        raise ApplyError(str(exc)) from exc
    root_obj = next((r for r in config.external_sources if r.source_root_key == args.root_key), None)
    if root_obj is None:
        raise ApplyError(f"Root key {args.root_key!r} not configured.")

    selected = _select_candidates(config, root_path, args.root_key, max_files=args.max_files,
                                  max_seconds=args.max_seconds, max_candidates=args.max_candidates,
                                  now_fn=now_fn)
    # Selection invariants (refuse rather than proceed on any violation).
    if len(selected) > args.max_candidates:
        raise ApplyError(f"Selected {len(selected)} > max_candidates {args.max_candidates}.")
    for r in selected:
        if r["disposition"] != "auto_card_high":
            raise ApplyError("Non-auto_card_high candidate selected.")
        if r["domain"] != "work":
            raise ApplyError("Non-work-domain candidate selected.")

    result: dict[str, Any] = {
        "mode": "apply" if args.apply else "preview", "root_key": args.root_key,
        "selected_count": len(selected), "enqueued_count": 0, "processed_count": 0,
        "generated_card_count": 0, "summary_count": 0, "skipped_count": 0, "error_count": 0,
        "counts_by_document_type": {}, "counts_by_disposition": {"auto_card_high": len(selected)},
        "all_routed_under_work": True,
    }
    detail_rows: list[dict[str, Any]] = []

    if not args.apply:
        # Preview only: report the selection, write nothing.
        for r in selected:
            result["counts_by_document_type"][r["document_type"]] = \
                result["counts_by_document_type"].get(r["document_type"], 0) + 1
            detail_rows.append({"rel_path": r["rel_path"], "document_type": r["document_type"]})
        result["detail_rows"] = detail_rows
        return result

    # ---- APPLY gates (production writes ahead) ----
    if args.confirm_root_key != args.root_key:
        raise ApplyError("--confirm-root-key must exactly match --root-key.")
    if args.confirm_db_path != args.db_path:
        raise ApplyError("--confirm-db-path must exactly match --db-path.")
    if args.confirm_vault_path != args.vault_path:
        raise ApplyError("--confirm-vault-path must exactly match --vault-path.")
    if _backend_listening():
        raise ApplyError("Refusing apply while a backend is listening on port 8000.")
    q0, p0 = _queue_counts(args.db_path)
    if args.require_empty_queue and (q0 != 0 or p0 != 0):
        raise ApplyError(f"Refusing apply: queue not empty (queued={q0}, processing={p0}).")

    repo = SourceIndexRepository(args.db_path)
    for r in selected:
        if result["generated_card_count"] >= args.max_cards:
            break
        abs_path = root_path / r["rel_path"]
        try:
            sid = index_source_file(abs_path, root_obj, repo, config)
        except Exception as exc:  # one bad file must not abort the bounded batch
            result["error_count"] += 1
            detail_rows.append({"rel_path": r["rel_path"], "error": type(exc).__name__})
            continue
        if sid is None:
            result["skipped_count"] += 1
            detail_rows.append({"rel_path": r["rel_path"], "skipped": "not_indexable"})
            continue
        result["processed_count"] += 1
        detail = repo.get_source_detail(sid)
        card_rel = _card_rel_path(config, detail)
        # Route + filename guards (hard stop — never write outside Work/ or replicate a source dir).
        if not card_rel.startswith("Source Notes/Work/"):
            raise ApplyError(f"Refusing: card would route outside Source Notes/Work/ ({card_rel!r}).")
        if ".." in card_rel or _domain_for(detail) != "work":
            raise ApplyError("Refusing: unsafe route/domain for a selected candidate.")
        try:
            out = generate_source_card(repo, config, source_id=sid, overwrite=False)
        except ObsidianMcpToolError as exc:
            if getattr(exc, "code", None) == "note_already_exists":
                result["skipped_count"] += 1  # never overwrite a user-authored file
                detail_rows.append({"rel_path": r["rel_path"], "skipped": "exists"})
                continue
            result["error_count"] += 1
            detail_rows.append({"rel_path": r["rel_path"], "error": getattr(exc, "code", "tool_error")})
            continue
        result["generated_card_count"] += 1
        result["counts_by_document_type"][r["document_type"]] = \
            result["counts_by_document_type"].get(r["document_type"], 0) + 1
        detail_rows.append({"rel_path": r["rel_path"], "source_id": sid, "note_path": out["note_path"]})

    # Post-apply assertion (req #2): the direct path must not have created any queue events.
    q1, p1 = _queue_counts(args.db_path)
    result["queue_after"] = {"queued": q1, "processing": p1}
    result["queued_event_delta"] = q1 - q0
    if q1 > q0:
        result["DEVIATION"] = f"queued events increased by {q1 - q0} (expected 0)."
    result["detail_rows"] = detail_rows
    return result


def main(argv: list[str] | None = None, *, now_fn: Callable[[], float] = time.monotonic) -> int:
    p = argparse.ArgumentParser(description="Bounded single-root first-indexing apply (preview by default).")
    p.add_argument("--db-path", required=True)
    p.add_argument("--config-path", required=True)
    p.add_argument("--vault-path", required=True)
    p.add_argument("--root-key", required=True)
    p.add_argument("--evidence-dir", default=None)
    p.add_argument("--max-files", type=int, default=500)
    p.add_argument("--max-seconds", type=float, default=120.0)
    p.add_argument("--max-candidates", type=int, default=25)
    p.add_argument("--max-events", type=int, default=25)  # direct path enqueues 0; kept for parity
    p.add_argument("--max-cards", type=int, default=25)
    p.add_argument("--max-summaries", type=int, default=0)
    p.add_argument("--require-empty-queue", action="store_true", default=True)
    p.add_argument("--no-require-empty-queue", dest="require_empty_queue", action="store_false")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--confirm-root-key", default="")
    p.add_argument("--confirm-db-path", default="")
    p.add_argument("--confirm-vault-path", default="")
    args = p.parse_args(argv)

    if args.max_summaries != 0:
        print(json.dumps({"refused": True,
                          "reason": "This bounded first batch requires --max-summaries 0."},
                         indent=2), file=sys.stderr)
        return 3
    try:
        result = run(args, now_fn=now_fn)
    except ApplyError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 3

    safe = {k: v for k, v in result.items() if k != "detail_rows"}
    if args.evidence_dir:
        ev = Path(args.evidence_dir)
        ev.mkdir(parents=True, exist_ok=True)
        (ev / f"first-indexing-apply-{args.root_key}-{result['mode']}-detail-local-sensitive.json").write_text(
            json.dumps({"root_key": args.root_key, "rows": result.get("detail_rows", [])},
                       indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (ev / f"first-indexing-apply-{args.root_key}-{result['mode']}-summary-safe.json").write_text(
            json.dumps(safe, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(safe, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
