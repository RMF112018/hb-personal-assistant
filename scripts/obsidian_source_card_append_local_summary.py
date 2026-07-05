#!/usr/bin/env python3
"""Bounded local-only advisory-summary appender for existing Obsidian source cards (Phase 10B).

For a bounded set of EXISTING generated Work source cards, calls local Ollama ``qwen2.5:14b`` and
replaces ONLY the card's ``hb-local-summary`` block with a sanitized advisory. Never touches
deterministic sections, never creates/deletes cards, never reads external source files, never scans
roots, never enqueues/drains, never calls a cloud model, never mutates the runtime JSON or the DB.

Default mode is dry-run (no Ollama call). ``--apply`` requires exact confirm flags + a clean runtime,
probes Ollama/model availability (fail-safe), and writes each card via the SHA-gated ``create_note``
path with a local-sensitive backup. DB metadata is fingerprinted before/after to PROVE no DB mutation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import socket
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import obsidian_source_first_indexing_dryrun as dryrun  # noqa: E402  (reuse _load_config)

from hb_assistant import naming  # noqa: E402
from hb_assistant.construction.classification.client import (  # noqa: E402
    OllamaChatClient,
    OllamaUnavailable,
    list_ollama_models,
)
from hb_assistant.obsidian_mcp import source_local_summary as sls  # noqa: E402
from hb_assistant.obsidian_mcp.mutations import create_note, sha256_file  # noqa: E402
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository  # noqa: E402
from hb_assistant.obsidian_mcp.source_notes import (  # noqa: E402
    CARD_VERSION,
    LOCAL_SUMMARY_BEGIN_PREFIX,  # noqa: F401  (re-exported; referenced by tests)
    LOCAL_SUMMARY_END,  # noqa: F401  (re-exported; referenced by tests)
    LOCAL_SUMMARY_MODEL,
    replace_local_summary_block,
)

BACKEND_PORT = 8000
_CANONICAL = [
    "## Source Summary", "## Why This Matters", "## PM Review Cues", "## Key Facts",
    "## Related Project", "## Related People / Companies", "## Related Decisions",
    "## Related Meetings", "## Source Basis", "## Advisory Summary", "## Follow-Up",
]


class AppendError(Exception):
    """Refusal — printed as a controlled error, exit code 3."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _backend_listening(port: int = BACKEND_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _ro_conn(db: str):
    return sqlite3.connect(f"file:{quote(db)}?mode=ro", uri=True)


def _queue_counts(db: str) -> tuple[int, int]:
    c = _ro_conn(db)
    try:
        row = c.execute(
            "SELECT COALESCE(SUM(status='queued'),0), COALESCE(SUM(status='processing'),0) "
            "FROM source_intelligence_events"
        ).fetchone()
    finally:
        c.close()
    return int(row[0] or 0), int(row[1] or 0)


def _db_fingerprint(db: str) -> dict[str, Any]:
    """Count-only + hash-only DB metadata snapshot (no row CONTENT is exported)."""
    c = _ro_conn(db)
    try:
        by_status = dict(c.execute(
            "SELECT generation_status, COUNT(*) FROM source_intelligence_generated_notes "
            "GROUP BY generation_status").fetchall())
        summaries = c.execute("SELECT COUNT(*) FROM source_intelligence_summaries").fetchone()[0]
        rows = c.execute(
            "SELECT source_id, note_rel_path, generation_status, generated_at "
            "FROM source_intelligence_generated_notes ORDER BY source_id, note_rel_path").fetchall()
    finally:
        c.close()
    meta = hashlib.sha256(repr(rows).encode("utf-8")).hexdigest()
    q, p = _queue_counts(db)
    return {"by_status": {str(k): int(v) for k, v in by_status.items()},
            "summaries_rows": int(summaries), "queued": q, "processing": p,
            "generated_note_meta_sha12": meta[:12]}


def _frontmatter_value(text: str, key: str) -> str | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    block = text[:end] if end != -1 else text
    import re
    m = re.search(rf"(?m)^{re.escape(key)}:\s*(.*?)\s*$", block)
    return (m.group(1).strip().strip('"') or None) if m else None


def _start_marker_status(text: str) -> str | None:
    for ln in text.splitlines():
        if naming.is_local_summary_begin(ln):
            import re
            m = re.search(r'status="([a-z_]+)"', ln)
            return m.group(1) if m else None
    return None


def _eligibility(text: str, note_rel: str, domain_folder: str, args: argparse.Namespace) -> str | None:
    """Return a refusal/ineligibility reason, or None if the card is eligible."""
    if ".." in note_rel or not note_rel.startswith(f"Source Notes/{domain_folder}/"):
        return "path_outside_domain"
    if not (text.startswith("---") and "\n---" in text):
        return "missing_frontmatter"
    if _frontmatter_value(text, "note_type") != "source_card":
        return "not_source_card"
    if not args.allow_non_current_version and _frontmatter_value(text, "card_version") != CARD_VERSION:
        return "card_version_mismatch"
    # Count the neutral and legacy marker forms (distinct string values in hb_assistant.naming);
    # a card carries exactly one, in either form. Do not use the re-exported source_notes constant
    # here — this slice aliases it to the legacy value, which would double-count a legacy card.
    begin = (text.count(naming.LOCAL_SUMMARY_BEGIN_PREFIX)
             + text.count(naming.LEGACY_LOCAL_SUMMARY_BEGIN_PREFIX))
    end = text.count(naming.LOCAL_SUMMARY_END) + text.count(naming.LEGACY_LOCAL_SUMMARY_END)
    if begin != 1 or end != 1:
        return "marker_count"
    status = _start_marker_status(text)
    if status == "generated" and not args.allow_resummarize:
        return "already_generated"
    if status not in ("pending", "generated"):
        return "marker_status"
    if [ln for ln in text.splitlines() if ln.startswith("## ")] != _CANONICAL:
        return "canonical_sections"
    return None


def _default_client_factory(model: str, timeout: float) -> OllamaChatClient:
    return OllamaChatClient(model=model, timeout=timeout)


def run(args: argparse.Namespace, *,
        client_factory: Callable[[str, float], Any] = _default_client_factory,
        now_iso_fn: Callable[[], str] = _now_iso) -> dict[str, Any]:
    if args.domain not in ("work", "home", "shared"):
        raise AppendError(f"unsupported domain: {args.domain}")
    domain_folder = {"work": "Work", "home": "Home", "shared": "Shared"}[args.domain]
    vault_root = Path(args.vault_path).resolve()
    config = dryrun._load_config(args.config_path)
    if Path(str(config.vault_root or "")).resolve() != vault_root:
        raise AppendError("config vault_root does not match --vault-path")
    repo = SourceIndexRepository(args.db_path)

    # Production invariant: total Work generated-note count must equal the expected baseline.
    fp_before = _db_fingerprint(args.db_path)
    work_generated = repo_work_generated(repo, domain_folder)
    if work_generated != args.expected_work_generated:
        raise AppendError(
            f"work generated count {work_generated} != expected {args.expected_work_generated}")

    prefix = f"Source Notes/{domain_folder}/"
    rows = sorted((r for r in repo.list_generated_notes(statuses=("generated",))
                   if str(r.get("note_rel_path") or "").startswith(prefix)),
                  key=lambda r: str(r["note_rel_path"]))

    selected, eligible, ineligible = [], [], []
    for row in rows:
        note_rel = str(row["note_rel_path"])
        target = vault_root / note_rel
        if not target.is_file():
            raise AppendError("target card file is missing")
        text = target.read_text(encoding="utf-8")
        reason = _eligibility(text, note_rel, domain_folder, args)
        selected.append(note_rel)
        if reason is None:
            eligible.append((row, target, text))
        else:
            ineligible.append((note_rel, reason))

    if len(eligible) > args.max_cards:
        raise AppendError(f"eligible {len(eligible)} exceeds --max-cards {args.max_cards}")

    detail_rows = [{"note_rel_path": nr, "ineligible_reason": rs} for nr, rs in ineligible]
    result: dict[str, Any] = {
        "mode": "apply" if args.apply else "dry-run",
        "model": args.model,
        "selected": len(selected),
        "eligible": len(eligible),
        "ineligible": len(ineligible),
        "summarized": 0, "skipped": len(ineligible), "failed": 0,
        "created": 0, "deleted": 0, "queue_delta": 0,
        "db_before": fp_before, "db_mutation_detected": False,
    }

    if not args.apply:
        # Dry-run NEVER calls Ollama.
        result["ollama_called"] = False
        return {"safe": result, "detail_rows": detail_rows}

    # ---- APPLY gates ---------------------------------------------------------------------------
    if not (args.confirm_db_path == args.db_path and args.confirm_vault_path == args.vault_path
            and args.confirm_model == args.model):
        raise AppendError("--apply requires matching --confirm-db-path/--confirm-vault-path/--confirm-model")
    if _backend_listening():
        raise AppendError("backend is listening on port 8000; refusing to write")
    q0, p0 = _queue_counts(args.db_path)
    if args.require_empty_queue and (q0 != 0 or p0 != 0):
        raise AppendError(f"queue not empty (queued={q0}, processing={p0})")

    # Ollama fail-safe probe BEFORE mutating any card.
    timeout = float(args.timeout_seconds or config.source_summary_ollama_timeout_seconds)
    client = client_factory(args.model, timeout)
    try:
        models = list_ollama_models(base_url=getattr(client, "base_url", None))
    except OllamaUnavailable as exc:
        raise AppendError(f"ollama_unavailable ({exc})") from None
    if args.model not in models:
        raise AppendError(f"model_unavailable: {args.model} not installed locally")
    result["ollama_models_count"] = len(models)

    backup_root = Path(args.backup_dir)
    generated_at = now_iso_fn()
    summarized = failed = created = deleted = 0
    for row, target, text in eligible:
        source_id = str(row["source_id"])
        note_rel = str(row["note_rel_path"])
        detail = repo.get_source_detail(source_id)
        if detail is None:
            failed += 1
            detail_rows.append({"note_rel_path": note_rel, "result": "failed",
                                "reason": "missing_source_record"})
            continue
        prompt = sls.build_summary_prompt(
            text, detail, max_input_chars=int(config.source_summary_max_input_chars))
        lines, reason = sls.generate_advisory(client, prompt)
        if lines is None:
            failed += 1  # model failure leaves the card UNCHANGED
            detail_rows.append({"note_rel_path": note_rel, "result": "failed", "reason": reason})
            continue
        new_text = replace_local_summary_block(text, lines, model=args.model,
                                               generated_at=generated_at)
        if not target.is_file():
            raise AppendError("apply would create a new card (target vanished)")
        backup_path = backup_root / note_rel
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup_path)
        out = create_note(config, path=note_rel, content=new_text, overwrite=True,
                          create_parent_dirs=False, expected_sha256=sha256_file(target),
                          caller_surface="mcp", tool_name="append_local_summary",
                          principal_kind="local")
        if out.get("created"):
            created += 1
        if not target.is_file():
            raise AppendError("apply deleted a target card (unexpected)")
        summarized += 1
        detail_rows.append({"note_rel_path": note_rel, "result": "summarized"})

    if created:
        raise AppendError(f"apply created {created} new cards (expected 0)")
    q1, p1 = _queue_counts(args.db_path)
    fp_after = _db_fingerprint(args.db_path)
    db_mutation = fp_after != fp_before
    result.update({
        "summarized": summarized, "failed": failed, "created": created, "deleted": deleted,
        "skipped": len(ineligible),
        "queue_before": q0, "queue_after": q1, "queue_delta": (q1 - q0),
        "db_after": fp_after, "db_mutation_detected": db_mutation,
        "ollama_called": True,
        "pilot_full_success": (failed == 0 and summarized == len(eligible)
                               and len(eligible) == args.expected_work_generated),
    })
    if (q1 - q0) != 0 or (p1 - p0) != 0:
        raise AppendError(f"queue changed during apply (delta queued={q1 - q0}, proc={p1 - p0})")
    if db_mutation:
        raise AppendError("DB metadata changed during apply (unexpected DB mutation)")
    return {"safe": result, "detail_rows": detail_rows}


def repo_work_generated(repo: SourceIndexRepository, domain_folder: str) -> int:
    prefix = f"Source Notes/{domain_folder}/"
    return sum(1 for r in repo.list_generated_notes(statuses=("generated",))
               if str(r.get("note_rel_path") or "").startswith(prefix))


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db-path", required=True)
    p.add_argument("--config-path",
                   default=str(Path.home() / "Library/Application Support/HB Personal Assistant"
                              / "analytics/obsidian_mcp_config.json"))
    p.add_argument("--vault-path", required=True)
    p.add_argument("--domain", default="work")
    p.add_argument("--model", default=LOCAL_SUMMARY_MODEL)
    p.add_argument("--max-cards", type=int, default=25)
    p.add_argument("--expected-work-generated", type=int, default=25)
    p.add_argument("--timeout-seconds", type=float, default=None)
    p.add_argument("--backup-dir", default=None)
    p.add_argument("--evidence-dir", default=None)
    p.add_argument("--json-output", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--confirm-db-path", default="")
    p.add_argument("--confirm-vault-path", default="")
    p.add_argument("--confirm-model", default="")
    p.add_argument("--require-empty-queue", action="store_true", default=True)
    p.add_argument("--no-require-empty-queue", dest="require_empty_queue", action="store_false")
    p.add_argument("--allow-resummarize", action="store_true")
    p.add_argument("--allow-non-current-version", action="store_true")
    return p


def main(argv: list[str] | None = None, *,
         client_factory: Callable[[str, float], Any] = _default_client_factory,
         now_iso_fn: Callable[[], str] = _now_iso) -> int:
    args = _build_parser().parse_args(argv)
    if args.apply and not args.backup_dir:
        print(json.dumps({"refused": True, "reason": "--apply requires --backup-dir"}), file=sys.stderr)
        return 3
    try:
        out = run(args, client_factory=client_factory, now_iso_fn=now_iso_fn)
    except AppendError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2), file=sys.stderr)
        return 3
    safe, detail_rows = out["safe"], out["detail_rows"]
    if args.evidence_dir:
        ev = Path(args.evidence_dir)
        ev.mkdir(parents=True, exist_ok=True)
        mode = safe["mode"]
        (ev / f"append-local-summary-{args.domain}-{mode}-summary-safe.json").write_text(
            json.dumps(safe, indent=2, sort_keys=True), encoding="utf-8")
        (ev / f"append-local-summary-{args.domain}-{mode}-detail-local-sensitive.json").write_text(
            json.dumps({"rows": detail_rows}, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(safe, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    print("NOTE: Phase 10J consolidated local enrichment into scripts/obsidian_source_enrich.py "
          "(--summaries); this standalone appender remains as the internal summary engine.",
          file=sys.stderr)
    raise SystemExit(main())
