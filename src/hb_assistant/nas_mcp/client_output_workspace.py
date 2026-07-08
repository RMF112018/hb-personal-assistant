"""N8C-24 — connected-client generated-output workspace repository.

Owns the staged → server-approved → idempotent commit lifecycle for generated files under the ``outputs``
root, plus receipts, a manifest, and staged archive. Trust model mirrors N8C-23 promotion: the server
mints the ``operator_approval_id`` (a client never supplies it) and derives the idempotency key from
``output_id + staged_content_hash + operator_approval_id``; commit recomputes the staged content hash and
fails closed on drift; a repeated commit with the same key returns the original receipt (no duplicate file).
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import borrow_connection, transaction

from . import client_output_path_resolver as resolver
from . import client_output_writers as writers
from .config import NasMcpConfig

_ALLOWED_CONTENT_MODES = frozenset({
    "text", "csv_text", "json_text", "markdown_text", "html_text", "base64_binary",
    "docx_from_markdown_or_text", "xlsx_from_csv", "pptx_from_markdown_or_json",
    "pdf_from_html_or_markdown", "zip_base64", "zip_from_outputs",
})
MAX_TITLE = 300
MAX_EXCERPT_CHARS = 4000


class ClientOutputError(ValueError):
    """A generated-output workspace operation failed a validation/trust check."""


def _now() -> str:
    from datetime import datetime, timezone  # noqa: PLC0415

    return datetime.now(timezone.utc).isoformat()


def _sha(*parts: Any) -> str:
    return writers.sha256_hex("|".join("" if p is None else str(p) for p in parts).encode("utf-8"))[:24]


def _cjson(obj: Any) -> str | None:
    return None if obj in (None, {}, []) else json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


_FILE_COLS = (
    "output_id", "title", "filename", "file_type", "content_mode", "status", "source_client",
    "source_session_id", "related_canonical_ids_json", "related_proposal_ids_json", "relative_path",
    "root_key", "path_display", "destination_state", "bytes_written", "sha256", "content_hash",
    "staged_content_hash", "staged_content_b64", "validation_summary_json", "zip_validation_json",
    "operator_approval_required", "operator_approval_id", "operator_approved_at", "idempotency_key",
    "receipt_id", "manifest_id", "created_by", "created_at", "committed_at", "archived_at", "updated_at",
)
_RECEIPT_COLS = ("receipt_id", "output_id", "receipt_type", "status", "relative_receipt_path",
                 "bytes_written", "sha256", "validation_summary_json", "created_at")
_PUBLIC_FILE_FIELDS = (
    "output_id", "title", "filename", "file_type", "content_mode", "status", "source_client",
    "source_session_id", "relative_path", "root_key", "path_display", "destination_state",
    "bytes_written", "sha256", "receipt_id", "created_at", "committed_at", "archived_at",
)


def _insert(c: Any, table: str, row: dict[str, Any]) -> None:
    cols = [k for k, v in row.items() if v is not None]
    c.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
              [row[k] for k in cols])


def _row(cur: Any, cols: tuple[str, ...]) -> dict[str, Any] | None:
    r = cur.fetchone()
    return dict(zip(cols, r, strict=True)) if r else None


class ClientOutputWorkspaceRepository:
    def __init__(self, config: NasMcpConfig, db_path: str | None = None) -> None:
        self.config = config
        self.db_path = db_path or str(config.db_path)

    # ---------- staging ----------
    def stage_output_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = str(payload.get("title") or "").strip()
        file_type = str(payload.get("file_type") or "").strip().lower().lstrip(".")
        content_mode = str(payload.get("content_mode") or "text").strip()
        content = payload.get("content_text")
        if content is None and payload.get("content_base64") is not None:
            content = payload["content_base64"]
            content_mode = "base64_binary" if file_type not in ("zip",) else content_mode
        content = "" if content is None else str(content)
        dest = str(payload.get("destination_state") or "pending").strip().lower()
        if not title:
            raise ClientOutputError("missing_title")
        if len(title) > MAX_TITLE:
            raise ClientOutputError("title_too_long")
        if content_mode not in _ALLOWED_CONTENT_MODES:
            raise ClientOutputError(f"invalid_content_mode:{content_mode}")
        resolver.validate_output_extension(self.config, file_type)  # raises on denied/unsupported

        # Render bytes now (validates content + ZIP safety) but DO NOT write the final file.
        data, extra = writers.render_output_bytes(
            config=self.config, file_type=file_type, content_mode=content_mode, content=content)
        staged_hash = writers.sha256_hex(data)
        now = _now()
        output_id = self._next_output_id(now)
        planned = resolver.resolve_output_relative_path(
            output_id=output_id, title=title, file_type=file_type, destination_state=dest,
            now=now, config=self.config)
        approval_id = _sha("output-appr", output_id, staged_hash)
        idem = _sha("output-idem", output_id, staged_hash, approval_id)
        zip_val = extra.get("zip_validation")
        row = {
            "output_id": output_id, "title": title, "filename": planned["filename"],
            "file_type": file_type, "content_mode": content_mode, "status": "staged",
            "source_client": payload.get("source_client"), "source_session_id": payload.get("source_session_id"),
            "related_canonical_ids_json": _cjson(payload.get("related_canonical_ids")),
            "related_proposal_ids_json": _cjson(payload.get("related_proposal_ids")),
            "relative_path": planned["resolved_relative_path"], "root_key": resolver.OUTPUT_ROOT_KEY,
            "path_display": planned["path_display"], "destination_state": dest,
            "sha256": staged_hash, "content_hash": staged_hash, "staged_content_hash": staged_hash,
            "staged_content_b64": base64.b64encode(data).decode("ascii"),
            "zip_validation_json": _cjson(zip_val), "operator_approval_required": 1,
            "operator_approval_id": approval_id, "idempotency_key": idem,
            "created_by": payload.get("operator_id"), "created_at": now, "updated_at": now,
        }
        with borrow_connection(None, self.db_path) as c, transaction(c):
            _insert(c, "assistant_output_files", row)
            _insert(c, "assistant_output_file_receipts", {
                "receipt_id": _sha("stage-rcpt", output_id, now), "output_id": output_id,
                "receipt_type": "stage", "status": "staged", "sha256": staged_hash,
                "validation_summary_json": _cjson({"bytes_estimated": len(data), "zip": zip_val}),
                "created_at": now})
        return {
            "output_id": output_id, "staged_status": "staged",
            "proposed_relative_path": planned["resolved_relative_path"], "file_type": file_type,
            "bytes_estimated": len(data), "sha256_preview": staged_hash,
            "operator_approval_id": approval_id, "idempotency_key": idem,
            "requires_operator_approval": True, "writes": False,
            "zip_validation": zip_val,
        }

    # ---------- commit ----------
    def commit_output_file(self, *, output_id: str, operator_approval_id: str,
                           idempotency_key: str | None = None, operator_id: str | None = None) -> dict[str, Any]:
        rec = self.get_output_file(output_id, include_content=True)
        if not rec:
            raise ClientOutputError("output_not_found")
        # idempotent short-circuit: already committed under the same key → return existing receipt.
        if rec["status"] == "committed" and rec.get("receipt_id"):
            existing = self.get_output_receipt(rec["receipt_id"])
            return {"output_id": output_id, "status": "committed", "idempotent_reuse": True,
                    "relative_path": rec["relative_path"], "sha256": rec["sha256"],
                    "receipt_id": rec["receipt_id"], "receipt": existing}
        if rec["status"] not in ("staged", "ready_to_commit"):
            raise ClientOutputError(f"not_committable_status:{rec['status']}")
        if str(operator_approval_id) != str(rec["operator_approval_id"]):
            raise ClientOutputError("operator_approval_mismatch")
        if idempotency_key is not None and str(idempotency_key) != str(rec["idempotency_key"]):
            raise ClientOutputError("idempotency_key_mismatch")
        # recompute integrity: staged bytes must still hash to the recorded staged hash.
        data = base64.b64decode(rec["staged_content_b64"])
        if writers.sha256_hex(data) != rec["staged_content_hash"]:
            raise ClientOutputError("staged_content_hash_mismatch")

        now = _now()
        write_meta = resolver.resolve_output_write_path(self.config, rec["relative_path"])
        target = Path(write_meta["absolute_path"])
        if target.exists():
            raise ClientOutputError("destination_exists")  # no silent overwrite; caller re-stages a version
        try:
            written = writers.write_output_bytes(target, data)
        except Exception as exc:  # noqa: BLE001 — record failure, surface honestly
            with borrow_connection(None, self.db_path) as c, transaction(c):
                c.execute("UPDATE assistant_output_files SET status='commit_failed', updated_at=? "
                          "WHERE output_id=?", (now, output_id))
                _insert(c, "assistant_output_file_receipts", {
                    "receipt_id": _sha("cf-rcpt", output_id, now), "output_id": output_id,
                    "receipt_type": "validation_failure", "status": "commit_failed",
                    "validation_summary_json": _cjson({"error": str(exc)}), "created_at": now})
            raise ClientOutputError(f"commit_write_failed:{exc}") from exc

        receipt_id = _sha("commit-rcpt", output_id, rec["idempotency_key"])
        receipt_rel = resolver.receipt_relative_path(output_id=output_id)
        with borrow_connection(None, self.db_path) as c, transaction(c):
            c.execute(
                "UPDATE assistant_output_files SET status='committed', bytes_written=?, sha256=?, "
                "operator_approved_at=?, receipt_id=?, committed_at=?, updated_at=?, staged_content_b64=NULL "
                "WHERE output_id=?",
                (written["bytes_written"], written["sha256"], now, receipt_id, now, now, output_id))
            _insert(c, "assistant_output_file_versions", {
                "output_version_id": _sha("ver", output_id, 1), "output_id": output_id, "version": 1,
                "filename": rec["filename"], "relative_path": rec["relative_path"],
                "bytes_written": written["bytes_written"], "sha256": written["sha256"],
                "created_by": operator_id, "created_at": now})
            _insert(c, "assistant_output_file_receipts", {
                "receipt_id": receipt_id, "output_id": output_id, "receipt_type": "commit",
                "status": "committed", "relative_receipt_path": receipt_rel,
                "bytes_written": written["bytes_written"], "sha256": written["sha256"],
                "validation_summary_json": rec.get("validation_summary_json"), "created_at": now})
            _insert(c, "assistant_output_file_manifest_entries", {
                "manifest_entry_id": _sha("ment", output_id), "output_id": output_id, "title": rec["title"],
                "file_type": rec["file_type"], "status": "committed", "relative_path": rec["relative_path"],
                "receipt_path": receipt_rel, "sha256": written["sha256"],
                "source_client": rec.get("source_client"), "source_session_id": rec.get("source_session_id"),
                "related_canonical_ids_json": rec.get("related_canonical_ids_json"),
                "created_at": now, "updated_at": now})
        return {
            "output_id": output_id, "status": "committed", "idempotent_reuse": False,
            "relative_path": rec["relative_path"], "root_key": resolver.OUTPUT_ROOT_KEY,
            "path_display": rec["path_display"], "bytes_written": written["bytes_written"],
            "sha256": written["sha256"], "receipt_id": receipt_id, "receipt_path": receipt_rel,
            "receipt_bytes": self._write_receipt_card(rec, receipt_rel, written, now),
            "manifest_updated": self._write_manifest(now),
        }

    # ---------- archive (staged, never delete) ----------
    def plan_archive_output(self, output_id: str) -> dict[str, Any]:
        rec = self.get_output_file(output_id)
        if not rec:
            raise ClientOutputError("output_not_found")
        if rec["status"] != "committed":
            raise ClientOutputError(f"only_committed_can_archive:{rec['status']}")
        target_rel = resolver.archive_relative_path(current_relative_path=rec["relative_path"], now=_now())
        return {"output_id": output_id, "current_relative_path": rec["relative_path"],
                "archive_relative_path": target_rel, "operation": "move_to_90_archive",
                "deletes": False, "requires_operator_approval": True, "writes": False}

    def commit_archive_output(self, *, output_id: str, operator_approval_id: str) -> dict[str, Any]:
        rec = self.get_output_file(output_id)
        if not rec:
            raise ClientOutputError("output_not_found")
        if str(operator_approval_id) != str(rec["operator_approval_id"]):
            raise ClientOutputError("operator_approval_mismatch")
        if rec["status"] == "archived":
            return {"output_id": output_id, "status": "archived", "idempotent_reuse": True,
                    "archive_relative_path": rec["relative_path"]}
        if rec["status"] != "committed":
            raise ClientOutputError(f"only_committed_can_archive:{rec['status']}")
        now = _now()
        src = Path(resolver.resolve_output_write_path(self.config, rec["relative_path"])["absolute_path"])
        target_rel = resolver.archive_relative_path(current_relative_path=rec["relative_path"], now=now)
        dst_meta = resolver.resolve_output_write_path(self.config, target_rel)
        dst = Path(dst_meta["absolute_path"])
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            import os  # noqa: PLC0415
            os.replace(str(src), str(dst))  # move, never delete
        receipt_id = _sha("arch-rcpt", output_id, now)
        with borrow_connection(None, self.db_path) as c, transaction(c):
            c.execute("UPDATE assistant_output_files SET status='archived', relative_path=?, archived_at=?, "
                      "updated_at=? WHERE output_id=?", (target_rel, now, now, output_id))
            c.execute("UPDATE assistant_output_file_manifest_entries SET status='archived', relative_path=?, "
                      "updated_at=? WHERE output_id=?", (target_rel, now, output_id))
            _insert(c, "assistant_output_file_receipts", {
                "receipt_id": receipt_id, "output_id": output_id, "receipt_type": "archive",
                "status": "archived", "relative_receipt_path": target_rel, "created_at": now})
        self._write_manifest(now)
        return {"output_id": output_id, "status": "archived", "idempotent_reuse": False,
                "archive_relative_path": target_rel, "receipt_id": receipt_id, "deletes": False}

    # ---------- reads ----------
    def list_output_files(self, *, status: str | None = None, file_type: str | None = None,
                          source_session_id: str | None = None, limit: int = 50) -> dict[str, Any]:
        where, args = [], []
        for col, val in (("status", status), ("file_type", file_type), ("source_session_id", source_session_id)):
            if val:
                where.append(f"{col}=?")
                args.append(val)
        sql = "SELECT " + ", ".join(_FILE_COLS) + " FROM assistant_output_files"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC LIMIT ?"
        args.append(min(int(limit), 200))
        with borrow_connection(None, self.db_path) as c:
            rows = [dict(zip(_FILE_COLS, r, strict=True)) for r in c.execute(sql, args).fetchall()]
        return {"outputs": [{k: r.get(k) for k in _PUBLIC_FILE_FIELDS} for r in rows], "count": len(rows)}

    def get_output_file(self, output_id: str, *, include_content: bool = False) -> dict[str, Any] | None:
        with borrow_connection(None, self.db_path) as c:
            row = _row(c.execute("SELECT " + ", ".join(_FILE_COLS) + " FROM assistant_output_files "
                                 "WHERE output_id=?", (output_id,)), _FILE_COLS)
        if row and not include_content:
            row.pop("staged_content_b64", None)
        return row

    def get_output_metadata(self, output_id: str) -> dict[str, Any]:
        row = self.get_output_file(output_id)
        if not row:
            raise ClientOutputError("output_not_found")
        return {k: row.get(k) for k in _PUBLIC_FILE_FIELDS} | {
            "related_canonical_ids": json.loads(row["related_canonical_ids_json"]) if row.get(
                "related_canonical_ids_json") else [],
            "zip_validation": json.loads(row["zip_validation_json"]) if row.get("zip_validation_json") else None,
        }

    def read_output_excerpt(self, output_id: str, *, max_chars: int = MAX_EXCERPT_CHARS) -> dict[str, Any]:
        row = self.get_output_file(output_id)
        if not row:
            raise ClientOutputError("output_not_found")
        ft = row["file_type"]
        if ft == "zip":
            return {"output_id": output_id, "file_type": ft, "preview_mode": "zip_members",
                    "zip_validation": json.loads(row["zip_validation_json"]) if row.get(
                        "zip_validation_json") else None, "note": "zip members listed; never extracted"}
        if ft in ("docx", "xlsx", "pptx", "pdf"):
            return {"output_id": output_id, "file_type": ft, "preview_mode": "metadata_only",
                    "bytes_written": row.get("bytes_written"), "sha256": row.get("sha256"),
                    "note": "binary office/pdf output — metadata only, no body extraction"}
        if row["status"] != "committed":
            return {"output_id": output_id, "file_type": ft, "preview_mode": "not_committed", "excerpt": None}
        target = Path(resolver.resolve_output_write_path(self.config, row["relative_path"])["absolute_path"])
        text = target.read_text(encoding="utf-8", errors="replace")[: min(int(max_chars), MAX_EXCERPT_CHARS)]
        return {"output_id": output_id, "file_type": ft, "preview_mode": "bounded_text_excerpt",
                "excerpt": text, "truncated": len(text) >= int(max_chars)}

    def get_output_receipt(self, receipt_id: str) -> dict[str, Any] | None:
        with borrow_connection(None, self.db_path) as c:
            return _row(c.execute("SELECT " + ", ".join(_RECEIPT_COLS) + " FROM assistant_output_file_receipts "
                                  "WHERE receipt_id=?", (receipt_id,)), _RECEIPT_COLS)

    def get_output_manifest(self) -> dict[str, Any]:
        cols = ("output_id", "title", "file_type", "status", "relative_path", "receipt_path", "sha256",
                "source_client", "source_session_id", "created_at")
        with borrow_connection(None, self.db_path) as c:
            rows = [dict(zip(cols, r, strict=True)) for r in c.execute(
                "SELECT " + ", ".join(cols) + " FROM assistant_output_file_manifest_entries "
                "ORDER BY created_at DESC LIMIT 500").fetchall()]
        return {"generated_at": _now(), "entry_count": len(rows), "entries": rows,
                "manifest_relative_paths": list(resolver.manifest_relative_paths())}

    def status_counts(self) -> dict[str, Any]:
        with borrow_connection(None, self.db_path) as c:
            def _one(sql: str, *a: Any) -> Any:
                r = c.execute(sql, a).fetchone()
                return r[0] if r else None
            pending = _one("SELECT COUNT(*) FROM assistant_output_files WHERE status IN ('staged','ready_to_commit')")
            committed = _one("SELECT COUNT(*) FROM assistant_output_files WHERE status='committed'")
            last_at = _one("SELECT MAX(committed_at) FROM assistant_output_files WHERE committed_at IS NOT NULL")
            last_rcpt = _one("SELECT receipt_id FROM assistant_output_file_receipts WHERE receipt_type='commit' "
                             "ORDER BY created_at DESC LIMIT 1")
        return {"pending_count": pending or 0, "committed_count": committed or 0,
                "last_write_at": last_at, "last_receipt_id": last_rcpt}

    # ---------- internal ----------
    def _next_output_id(self, now: str) -> str:
        day = now[:10].replace("-", "")
        prefix = f"OUTPUT-{day}-"
        with borrow_connection(None, self.db_path) as c:
            n = c.execute("SELECT COUNT(*) FROM assistant_output_files WHERE output_id LIKE ?",
                          (prefix + "%",)).fetchone()[0]
        return f"{prefix}{n + 1:03d}"

    def _receipt_markdown(self, rec: dict[str, Any], written: dict[str, Any], now: str) -> str:
        rel = rec["relative_path"]
        zipv = json.loads(rec["zip_validation_json"]) if rec.get("zip_validation_json") else None
        lines = [
            f"# {rec['output_id']} — Output File Receipt", "", "## Summary", "",
            "Generated file written to the client output workspace.", "", "## File", "",
            f"- Title: {rec['title']}", f"- File type: {rec['file_type']}",
            f"- Relative path: `{rel}`", f"- Root: `{resolver.OUTPUT_ROOT_KEY}`", "- Status: committed", "",
            "## Provenance", "", f"- Source client: {rec.get('source_client') or 'n/a'}",
            f"- Source session: {rec.get('source_session_id') or 'n/a'}", "", "## Integrity", "",
            f"- Bytes written: {written['bytes_written']}", f"- SHA256: {written['sha256']}",
            f"- Content mode: {rec['content_mode']}", "", "## Validation", "",
            "- Path validation: passed", "- Extension validation: passed", "- Size validation: passed",
            f"- ZIP validation: {'passed' if zipv else 'not applicable'}", "", "## Timestamps", "",
            f"- Committed at: {now}",
        ]
        if zipv:
            lines += ["", "## ZIP Validation", "", f"- Member count: {zipv.get('member_count')}",
                      f"- Compressed bytes: {zipv.get('compressed_bytes')}",
                      f"- Declared uncompressed bytes: {zipv.get('declared_uncompressed_bytes')}",
                      "- Encrypted members: none", "- Path traversal: none", "- Absolute member paths: none"]
        return "\n".join(lines) + "\n"

    def _write_receipt_card(self, rec: dict[str, Any], receipt_rel: str, written: dict[str, Any],
                            now: str) -> int:
        meta = resolver.resolve_output_write_path(self.config, receipt_rel)
        md = self._receipt_markdown(rec, written, now)
        writers.write_output_bytes(Path(meta["absolute_path"]), md.encode("utf-8"))
        return len(md)

    def _write_manifest(self, now: str) -> bool:
        manifest = self.get_output_manifest()
        md_rel, json_rel = resolver.manifest_relative_paths()
        lines = ["# Client Output Manifest", "", f"generated_at: {now}",
                 f"entries: {manifest['entry_count']}", "", "| output_id | type | status | path |",
                 "| --- | --- | --- | --- |"]
        for e in manifest["entries"]:
            lines.append(f"| {e['output_id']} | {e['file_type']} | {e['status']} | `{e['relative_path']}` |")
        writers.write_output_bytes(
            Path(resolver.resolve_output_write_path(self.config, md_rel)["absolute_path"]),
            ("\n".join(lines) + "\n").encode("utf-8"))
        writers.write_output_bytes(
            Path(resolver.resolve_output_write_path(self.config, json_rel)["absolute_path"]),
            json.dumps(manifest["entries"], indent=2, default=str).encode("utf-8"))
        return True
