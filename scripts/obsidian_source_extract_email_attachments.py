#!/usr/bin/env python3
"""Bounded email-attachment extraction + attachment source cards (Phase 10F).

For ≤N already-Phase-10E-carded `.eml` files under ONE allowlisted project folder, this re-parses each
email for attachment BYTES. Attachment binaries are extracted TRANSIENTLY under the guarded
``Email Archive/Work/Attachments/`` root only long enough to index + card each attachment through the
deterministic source-card pipeline (via a synthetic 'work' attachment root so cards land in
``Source Notes/Work/``), then ALWAYS deleted (empty dirs pruned) — this phase creates NO retained
attachment binary archive. It also writes **reciprocal** managed-block links between the parent email
card and its attachment cards, and reconciles inherited project identity so each attachment card's
frontmatter + visible "Related Project" line agree with its hb-project-identity block.

DETERMINISTIC-ONLY by default — NO Ollama, NO queue/watcher, NO scan outside the root, NO runtime-JSON
mutation, NO general note-graph links/tags (lineage-only; broader graph apply is Phase 10G). Each
attachment card's hb-local-summary block is left PENDING. The local qwen2.5:14b advisory summary is an
OPERATOR-ONLY opt-in behind ``--summarize`` and is written only if it passes the quality gate
(``sls.validate_advisory``); otherwise the block stays pending (``summary_failed``). Default is dry-run;
``--apply`` requires exact confirm flags + a rollback bundle. Inline images are counted only (no
binary/card). Unsafe executable/script and oversize attachments are never written — reported with an
explicit skip reason. Reciprocal links are written email-atomically (all links + parent block, or none);
a failed rollback is a hard stop.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import obsidian_source_first_indexing_dryrun as dryrun  # noqa: E402
import obsidian_source_index_eml_archive as eml10e  # noqa: E402 — reuse 10E infra + gates

from hb_assistant.construction.classification.client import OllamaChatClient  # noqa: E402
from hb_assistant.obsidian_mcp import source_email_attachments as att  # noqa: E402
from hb_assistant.obsidian_mcp import source_local_summary as sls  # noqa: E402
from hb_assistant.obsidian_mcp import source_project_identity as spi  # noqa: E402
from hb_assistant.obsidian_mcp.config import ExternalSourceRoot  # noqa: E402
from hb_assistant.obsidian_mcp.mutations import create_note, sha256_file  # noqa: E402
from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository  # noqa: E402
from hb_assistant.obsidian_mcp.source_indexer import index_source_file  # noqa: E402
from hb_assistant.obsidian_mcp.source_notes import (  # noqa: E402
    _card_rel_path,
    generate_source_card,
    replace_local_summary_block,
)
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError  # noqa: E402

# Reuse the 10E refusal exception (exit 3) so _resolve_identity's raises are caught uniformly.
AttachError = eml10e.EmlArchiveError
# Synthetic attachment source root key — contains 'work' so cards route to Source Notes/Work/.
ATTACH_ROOT_KEY = "syn-work-email-attachments"
# Phase 10F is DETERMINISTIC-ONLY by default: the default apply makes NO Ollama call and leaves each
# attachment card's hb-local-summary block PENDING. The local advisory summarizer (pinned to qwen2.5:14b;
# config default is llama3.1 for other flows) runs ONLY under the explicit operator-only `--summarize`
# flag, and even then writes only when the output passes the quality gate (sls.validate_advisory).
SUMMARY_MODEL = "qwen2.5:14b"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_client_factory(model: str, timeout: float) -> OllamaChatClient:
    return OllamaChatClient(model=model, timeout=timeout)


_SKIP_STATUS = {"skipped_unsafe_type": "skipped_unsafe", "skipped_size_cap": "skipped_oversize",
                "skipped_empty": "skipped_empty", "duplicate": "duplicates"}


def _new_result(mode: str, ident: Any, sel: dict[str, Any], selected: list[Path],
                db_path: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "project_number": ident.project_number, "project_key": ident.project_key,
        "procore_project_id": ident.procore_project_id,
        "eml_found": sel["readable_seen"], "cloud_evicted": sel["cloud_evicted"],
        "emails_selected": len(selected),
        "emails_with_attachments": 0, "emails_skipped_no_parent_card": 0, "eml_parse_failed": 0,
        "inline_parts": 0, "attachments_discovered": 0, "attachments_extractable": 0,
        "skipped_unsafe": 0, "skipped_oversize": 0, "skipped_empty": 0, "duplicates": 0,
        # amendment #5: distinct accounting — binaries/archives are NOT generated notes.
        "attachment_binaries_written": 0, "metadata_only_attachments": 0,
        # binaries are TRANSIENT: written only to card, then always deleted (not gated on qwen).
        "attachment_binaries_deleted": 0,
        "attachment_cards_generated": 0, "attachment_cards_updated": 0,
        "already_indexed": 0, "skipped_unavailable": 0,
        "parent_email_cards_updated": 0, "reciprocal_links_added": 0,
        # opt-in (--summarize) local qwen2.5:14b advisories: written only if they pass the quality gate;
        # summary_failed counts model failures + gate rejections (block left deterministic/pending).
        "qwen_summaries_written": 0, "summary_failed": 0,
        "generated_note_delta": 0, "vault_markdown_delta": 0, "queue_delta": 0, "ollama_calls": 0,
        "generated_before": eml10e._generated_counts(db_path),
    }


def _parent_context(p: Path, base: Path, repo: SourceIndexRepository, config: Any, vault_root: Path,
                    ) -> dict[str, Any] | None:
    """Resolve the parent email source_id + existing card/archive paths, or None if not 10E-carded."""
    rel = str(p.resolve().relative_to(base))
    existing = repo.lookup_by_path("external_file", rel)
    if not existing:
        return None
    parent_sid = existing["source_id"]
    if not repo.has_generated_note(parent_sid):
        return None
    detail = repo.get_source_detail(parent_sid) or {}
    card_rel = _card_rel_path(config, detail)
    if not (vault_root / card_rel).is_file():
        return None
    return {"sid": parent_sid, "detail": detail, "card_rel": card_rel,
            "archive_rel": eml10e._archive_rel_path(detail)}


def _discover(p: Path, base: Path, repo: SourceIndexRepository, config: Any, vault_root: Path,
              args: argparse.Namespace, result: dict[str, Any]) -> None:
    """Dry-run: read-only attachment discovery + counts. Writes nothing."""
    ctx = _parent_context(p, base, repo, config, vault_root)
    if ctx is None:
        result["emails_skipped_no_parent_card"] += 1
        return
    extracted, inline = att.extract_attachments(p.resolve(), max_bytes=args.max_attachment_bytes)
    result["inline_parts"] += inline
    if extracted and extracted[0].status == "parse_failed":
        result["eml_parse_failed"] += 1
        return
    if extracted:
        result["emails_with_attachments"] += 1
    for e in extracted:
        if result["attachments_discovered"] >= args.max_attachments:
            break
        result["attachments_discovered"] += 1
        if e.status in _SKIP_STATUS:
            result[_SKIP_STATUS[e.status]] += 1
        else:
            result["attachments_extractable"] += 1
            if e.status == "metadata_only":
                result["metadata_only_attachments"] += 1


def _maybe_summarize(att_card_rel: str, att_sid: str, vault_root: Path, config: Any,
                     repo: SourceIndexRepository, client: Any, now_iso: str,
                     result: dict[str, Any], detail_rows: list[dict[str, Any]]) -> None:
    """Opt-in (--summarize) local qwen2.5:14b advisory into the card's hb-local-summary block.

    Reached only when a client was built (i.e. --summarize). Never raises and never gates binary
    deletion. The summary is WRITTEN only if it passes ``sls.validate_advisory`` (canonical 4-section
    shape; no filename/size assertion or deterministic-metadata contradiction; no duplicate/noncanonical
    shape); otherwise the block is left deterministic/pending and ``summary_failed`` is incremented.
    Reads only DB detail + the card text — never the (already-deleted-later) attachment binary.
    """
    if client is None:
        return
    card_abs = vault_root / att_card_rel
    try:
        card_text = card_abs.read_text(encoding="utf-8")
        detail = repo.get_source_detail(att_sid) or {}
        prompt = sls.build_summary_prompt(
            card_text, detail, max_input_chars=int(config.source_summary_max_input_chars))
        lines, reason = sls.generate_advisory(client, prompt)
        result["ollama_calls"] += 1
        if lines is None:
            result["summary_failed"] += 1
            detail_rows.append({"summary": "failed", "reason": reason})
            return
        ok, vreason = sls.validate_advisory(lines, detail)
        if not ok:
            result["summary_failed"] += 1  # leave the pending/deterministic block untouched
            detail_rows.append({"summary": "failed", "reason": vreason})
            return
        new_text = replace_local_summary_block(card_text, lines, model=SUMMARY_MODEL,
                                               generated_at=now_iso)
        if new_text != card_text:
            create_note(config, path=att_card_rel, content=new_text, overwrite=True,
                        create_parent_dirs=False, expected_sha256=sha256_file(card_abs),
                        caller_surface="mcp", tool_name="attachment_local_summary",
                        principal_kind="local")
            result["qwen_summaries_written"] += 1
    except Exception as exc:  # noqa: BLE001 — advisory summary is strictly best-effort
        result["summary_failed"] += 1
        detail_rows.append({"summary": "error", "reason": str(exc)[:120]})


def _apply_email(p: Path, base: Path, repo: SourceIndexRepository, config: Any, vault_root: Path,
                 ident: spi.ProjectIdentity, synth_root: ExternalSourceRoot, attach_root_path: Path,
                 args: argparse.Namespace, backup_root: Path, result: dict[str, Any],
                 detail_rows: list[dict[str, Any]], client: Any, now_iso: str) -> None:
    ctx = _parent_context(p, base, repo, config, vault_root)
    if ctx is None:
        result["emails_skipped_no_parent_card"] += 1
        detail_rows.append({"skip": "parent_email_not_carded"})
        return
    parent_sid, parent_card_rel, parent_archive_rel = ctx["sid"], ctx["card_rel"], ctx["archive_rel"]
    parent_card_abs = vault_root / parent_card_rel

    extracted, inline = att.extract_attachments(p.resolve(), max_bytes=args.max_attachment_bytes)
    result["inline_parts"] += inline
    if extracted and extracted[0].status == "parse_failed":
        result["eml_parse_failed"] += 1
        detail_rows.append({"skip": "parse_failed"})
        return
    if not extracted:
        return
    result["emails_with_attachments"] += 1

    # ---- phase 1: extract binaries + index + generate base cards for safe attachments ----
    planned: list[dict[str, Any]] = []
    for e in extracted:
        if result["attachments_discovered"] >= args.max_attachments:
            break
        result["attachments_discovered"] += 1
        if e.status in _SKIP_STATUS:
            result[_SKIP_STATUS[e.status]] += 1
            detail_rows.append({"skip": e.status})
            continue
        result["attachments_extractable"] += 1
        att_rel = att.attachment_rel_path(parent_sid, e)
        # Write the binary ONLY long enough to index + card (+ optionally summarize) it; the finally
        # block ALWAYS deletes it afterward so no attachment binary ever persists in the vault.
        wstat = att.write_attachment_binary(vault_root, att_rel, e.data or b"", overwrite=True)
        if wstat == "written":
            result["attachment_binaries_written"] += 1
        try:
            att_abs = vault_root / att_rel
            rel_to_root = str(att_abs.resolve().relative_to(attach_root_path.resolve()))
            existing_att = repo.lookup_by_path("external_file", rel_to_root)
            if existing_att and not args.update:
                result["already_indexed"] += 1
                continue
            att_sid = index_source_file(att_abs, synth_root, repo, config)
            if att_sid is None:
                result["skipped_unavailable"] += 1
                continue
            att_detail = repo.get_source_detail(att_sid) or {}
            att_card_rel = _card_rel_path(config, att_detail)
            carded = repo.has_generated_note(att_sid)
            try:
                generate_source_card(repo, config, source_id=att_sid, overwrite=args.update,
                                     principal_kind="local")
            except ObsidianMcpToolError as exc:
                if exc.code == "note_already_exists":
                    carded = True
                else:
                    result["skipped_unavailable"] += 1
                    detail_rows.append({"skip": exc.code})
                    continue
            if carded:
                result["attachment_cards_updated"] += 1
            else:
                result["attachment_cards_generated"] += 1
            if e.status == "metadata_only":
                result["metadata_only_attachments"] += 1
            # best-effort qwen summary BEFORE the binary is deleted (reads DB detail, not the binary).
            _maybe_summarize(att_card_rel, att_sid, vault_root, config, repo, client, now_iso,
                             result, detail_rows)
            planned.append({"e": e, "card_rel": att_card_rel,
                            "facts": att.attachment_card_facts(parent_sid, e)})
        finally:
            # amendment: binaries are transient — delete regardless of card/qwen outcome.
            if att.delete_attachment_binary(vault_root, att_rel):
                result["attachment_binaries_deleted"] += 1

    if not planned:
        return

    # ---- phase 2: email-atomic reciprocal link write (all links + parent block, or none) ----
    targets = [parent_card_rel] + [pl["card_rel"] for pl in planned]
    backups: dict[str, Path | None] = {}
    for rel in targets:
        abs_ = vault_root / rel
        bpath = backup_root / "cards" / rel
        bpath.parent.mkdir(parents=True, exist_ok=True)
        if abs_.is_file():
            shutil.copy2(abs_, bpath)
            backups[rel] = bpath
        else:
            backups[rel] = None
    try:
        for pl in planned:
            abs_ = vault_root / pl["card_rel"]
            text = abs_.read_text(encoding="utf-8")
            s1, _r1 = spi.enrich_card_with_project_identity(text, ident)  # inherited parent identity
            working = s1 if s1 is not None else text
            s2, r2 = att.enrich_card_with_attachment(working, pl["facts"], parent_card_rel,
                                                     parent_archive_rel)
            if s2 is None:
                raise AttachError(f"attachment link block failed: {r2}")
            # Reconcile inherited identity so frontmatter + the visible "Related Project" bullet agree
            # with the hb-project-identity block (no self-contradiction). Idempotent; block untouched.
            s3 = att.apply_inherited_project_frontmatter(
                s2, project_number=ident.project_number, project_key=ident.project_key)
            s3 = att.reconcile_related_project_line(
                s3, project_number=ident.project_number, project_key=ident.project_key,
                project_name=getattr(ident, "project_name", None))
            if s3 != text:
                create_note(config, path=pl["card_rel"], content=s3, overwrite=True,
                            create_parent_dirs=False, expected_sha256=sha256_file(abs_),
                            caller_surface="mcp", tool_name="enrich_attachment_card",
                            principal_kind="local")
        ptext = parent_card_abs.read_text(encoding="utf-8")
        entries = [(pl["card_rel"], pl["e"].status) for pl in planned]
        ptxt2, pr = att.upsert_email_attachments_block(ptext, entries)
        if ptxt2 is None:
            raise AttachError(f"parent attachments block failed: {pr}")
        if ptxt2 != ptext:
            create_note(config, path=parent_card_rel, content=ptxt2, overwrite=True,
                        create_parent_dirs=False, expected_sha256=sha256_file(parent_card_abs),
                        caller_surface="mcp", tool_name="link_email_attachments",
                        principal_kind="local")
        result["parent_email_cards_updated"] += 1
        result["reciprocal_links_added"] += len(planned)
    except Exception as exc:  # noqa: BLE001 — reciprocal-or-neither
        for rel, bpath in backups.items():
            abs_ = vault_root / rel
            try:
                if bpath is None:
                    if abs_.is_file():
                        abs_.unlink()
                else:
                    shutil.copy2(bpath, abs_)
            except OSError as rexc:
                raise AttachError(f"rollback_failed for email pair: {rexc}") from exc
        detail_rows.append({"skip": "reciprocal_rollback", "reason": str(exc)[:120]})


def run(args: argparse.Namespace, *,
        client_factory: Callable[[str, float], Any] | None = None,
        now_iso_fn: Callable[[], str] | None = None) -> dict[str, Any]:
    # Resolve via module globals at call time so tests can monkeypatch the defaults.
    client_factory = client_factory or _default_client_factory
    now_iso_fn = now_iso_fn or _now_iso
    vault_root = Path(args.vault_path).resolve()
    config = dryrun._load_config(args.config_path)
    if Path(str(config.vault_root or "")).resolve() != vault_root:
        raise AttachError("config vault_root does not match --vault-path")
    source_root = Path(args.source_root).resolve()
    if (args.apply or args.confirm_source_root) and \
            str(source_root) != str(Path(args.confirm_source_root).resolve()):
        raise AttachError("--source-root does not match --confirm-source-root")
    if not source_root.is_dir():
        raise AttachError("source root is not a directory")
    root_obj = next((r for r in config.external_sources if r.source_root_key == args.root_key), None)
    if root_obj is None:
        raise AttachError(f"root-key {args.root_key} not in config external_sources")
    base = Path(root_obj.path).resolve()
    if not (source_root == base or base in source_root.parents):
        raise AttachError("source root is not under the configured external root")

    ident = eml10e._resolve_identity(source_root, args.db_path, args)
    repo = SourceIndexRepository(args.db_path)
    sel = eml10e._select_eml(source_root, max_files=args.max_eml)
    selected = sel["selected"]
    attach_root_path = vault_root / att.ATTACHMENTS_SUBDIR
    synth_root = ExternalSourceRoot(source_root_key=ATTACH_ROOT_KEY, path=str(attach_root_path),
                                    enabled=True)

    result = _new_result("apply" if args.apply else "dry-run", ident, sel, selected, args.db_path)
    detail_rows: list[dict[str, Any]] = []

    if not args.apply:
        for p in selected:
            _discover(p, base, repo, config, vault_root, args, result)
        return {"safe": result, "detail_rows": detail_rows, "identity": ident}

    # ---- APPLY gates + rollback bundle (mirror Phase 10E) ----
    if not (args.confirm_db_path == args.db_path and args.confirm_vault_path == args.vault_path):
        raise AttachError("--apply requires matching --confirm-db-path/--confirm-vault-path")
    if any(getattr(config, f, False) for f in eml10e._FROZEN_FLAGS):
        raise AttachError("runtime frozen flags are not all false")
    if eml10e._backend_listening():
        raise AttachError("backend listening on port 8000")
    q0, p0 = eml10e._queue_counts(args.db_path)
    if args.require_empty_queue and (q0 or p0):
        raise AttachError(f"queue not empty (queued={q0}, processing={p0})")
    if not args.backup_dir:
        raise AttachError("no rollback bundle: --backup-dir required for apply")
    backup_root = Path(args.backup_dir)
    backup_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.db_path, backup_root / "db-backup.sqlite")
    sn_dir = vault_root / (config.source_notes_folder or "Source Notes").strip("/")
    before_cards = sorted(str(x.relative_to(vault_root)) for x in sn_dir.rglob("*.md")) \
        if sn_dir.is_dir() else []
    ea_dir = vault_root / att.ATTACHMENTS_SUBDIR
    before_atts = sorted(str(x.relative_to(vault_root)) for x in ea_dir.rglob("*")) \
        if ea_dir.is_dir() else []
    (backup_root / "rollback-manifest.json").write_text(json.dumps({
        "db_backup": "db-backup.sqlite", "source_notes_md_before": before_cards,
        "attachments_before": before_atts,
        "restore": "restore db-backup.sqlite over the live DB, delete Source Notes cards created after "
                   "this run, and delete Email Archive/Work/Attachments files not in attachments_before",
    }, indent=2), encoding="utf-8")

    # DETERMINISTIC-ONLY DEFAULT: build an Ollama client (and later summarize) ONLY under the explicit
    # operator-only --summarize flag. Without it, no client is built, no Ollama call is made, and each
    # attachment card keeps its deterministic PENDING hb-local-summary block.
    client: Any = None
    if args.summarize:
        timeout = float(args.timeout_seconds or config.source_summary_ollama_timeout_seconds)
        try:
            client = client_factory(SUMMARY_MODEL, timeout)
        except Exception as exc:  # noqa: BLE001 — never block carding on summarizer setup
            result["summary_client_error"] = str(exc)[:120]
            client = None
    result["summarize_requested"] = bool(args.summarize)
    result["summary_model"] = SUMMARY_MODEL if client is not None else None
    now_iso = now_iso_fn()

    for p in selected:
        _apply_email(p, base, repo, config, vault_root, ident, synth_root, attach_root_path, args,
                     backup_root, result, detail_rows, client, now_iso)

    q1, p1 = eml10e._queue_counts(args.db_path)
    result["queue_after"] = q1
    result["queue_delta"] = q1 - q0
    gen_after = eml10e._generated_counts(args.db_path)
    result["generated_after"] = gen_after
    result["generated_note_delta"] = sum(gen_after.values()) - sum(result["generated_before"].values())
    result["vault_markdown_delta"] = result["attachment_cards_generated"]
    if (q1 - q0) or (p1 - p0):
        raise AttachError("queue changed during apply")
    return {"safe": result, "detail_rows": detail_rows, "identity": ident}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db-path", required=True)
    p.add_argument("--config-path",
                   default=str(Path.home() / "Library/Application Support/HB Personal Assistant"
                              / "analytics/obsidian_mcp_config.json"))
    p.add_argument("--vault-path", required=True)
    p.add_argument("--source-root", required=True)
    p.add_argument("--root-key", default="syn-work")
    p.add_argument("--max-eml", type=int, default=10)
    p.add_argument("--max-attachments", type=int, default=50)
    p.add_argument("--max-attachment-bytes", type=int, default=att.DEFAULT_MAX_ATTACHMENT_BYTES)
    p.add_argument("--summarize", action="store_true",
                   help="OPERATOR-ONLY opt-in: run the local qwen2.5:14b advisory summary, writing it "
                        "ONLY if it passes the quality gate. Default (omitted) is deterministic-only: no "
                        "Ollama call, hb-local-summary stays pending.")
    p.add_argument("--timeout-seconds", type=float, default=None)
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
    except AttachError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2), file=sys.stderr)
        return 3
    safe, detail_rows = out["safe"], out["detail_rows"]
    if args.evidence_dir:
        ev = Path(args.evidence_dir)
        ev.mkdir(parents=True, exist_ok=True)
        mode = safe["mode"]
        (ev / f"eml-attachments-{mode}-summary-safe.json").write_text(
            json.dumps(safe, indent=2, sort_keys=True), encoding="utf-8")
        (ev / f"eml-attachments-{mode}-detail-local-sensitive.json").write_text(
            json.dumps({"rows": detail_rows}, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(safe, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
