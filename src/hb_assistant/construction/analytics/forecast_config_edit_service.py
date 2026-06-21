"""Forecast config-edit proposals (Implementation Phase E) — first config-WRITE surface.

An operator proposes edits to forecast config items; this service seeds a base config tree from a
chosen **live** snapshot (opened ``mode=ro`` — the live DB is never written and is never handed to a
CFR function), applies the validated edits in an isolated per-edit directory under a fail-closed
**config-edit root**, then runs the CFR config pipeline (``import → snapshot → materialize → parity``)
into an **isolated** temp DB and returns a parity-proven materialized snapshot + a redacted report.

Zero live-DB writes, zero live-data-root writes. A later phase can certify-promote a proposal; that
is out of scope. Confined to the config-edit root (mirrors ``forecast_external_eval_service``); CFR is
not pip-installed so the subrepo ``src`` is injected onto ``sys.path`` (reusing the Phase 3 helper).
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.analytics import forecast_config_edit_dto as dto
from hb_assistant.construction.analytics.forecast_dto import friendly_datetime_from_stamp
from hb_assistant.construction.analytics.forecast_run_service import (
    ENV_CFR_SRC,
    _ensure_cfr_importable,
)
from hb_assistant.construction.analytics.forecast_runtime_config import ENV_CONFIG_EDIT_ROOT

ENV_DATA_ROOT = "HB_FORECAST_DATA_ROOT"  # the live data root; the config-edit root must be outside it

_SURFACE = "analytics.forecast_config_edit"
_EDITS_DIRNAME = "edits"
_EDIT_RECORD = "edit_record.json"
_SUPPORTED_PROJECT = "tropical"

ForecastConfigEditError = dto.ForecastConfigEditError


def resolve_config_edit_root(override: str | None = None) -> Path:
    """Fail-closed config-edit root: absolute, creatable, and never under the live data root."""
    raw = override or os.environ.get(ENV_CONFIG_EDIT_ROOT)
    if not raw:
        raise ForecastConfigEditError("forecast config-edit root is not configured")
    p = Path(raw)
    if not p.is_absolute():
        raise ForecastConfigEditError("forecast config-edit root must be an absolute path")
    live = os.environ.get(ENV_DATA_ROOT)
    if live and _is_under(p, Path(live)):
        raise ForecastConfigEditError("forecast config-edit root must not be under the live data root")
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ForecastConfigEditError("forecast config-edit root could not be created") from exc
    return p


def _is_under(child: Path, parent: Path) -> bool:
    try:
        c = child.resolve(strict=False)
        r = parent.resolve(strict=False)
        return c == r or c.is_relative_to(r)
    except OSError:
        return True  # fail closed


def _guardrails() -> dict[str, Any]:
    return {
        "writes_isolated_config_edit_root": True,
        "no_live_db_write": True,
        "no_live_data_root_write": True,
        "no_llm": True,
        "no_live_endpoint_calls": True,
        "local_first": True,
    }


class ForecastConfigEditService:
    """Proposes isolated config edits and lists/reads prior proposals."""

    def __init__(
        self,
        config_edit_root: str | None = None,
        db_path: str | None = None,
        cfr_src: str | None = None,
    ) -> None:
        self._config_edit_root_override = config_edit_root
        self._db_path_override = db_path
        self._cfr_src_override = cfr_src

    # -- config / fail-closed -------------------------------------------------

    def _edits_root(self) -> Path:
        root = resolve_config_edit_root(self._config_edit_root_override) / _EDITS_DIRNAME
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _live_db_path(self) -> Path:
        raw = self._db_path_override or str(PathPolicy().get_db_path())
        p = Path(raw)
        if not p.exists():
            raise ForecastConfigEditError("forecast config DB is not available")
        return p

    def _connect_ro(self) -> sqlite3.Connection:
        """Open the live source DB read-only. mode=ro fails if it cannot be opened read-only."""
        p = self._live_db_path()
        try:
            conn = sqlite3.connect(f"{p.resolve().as_uri()}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as exc:
            raise ForecastConfigEditError("forecast config DB could not be opened read-only") from exc

    # -- public API -----------------------------------------------------------

    def propose_config_edit(
        self, base_snapshot_id: str, edits: Any, project_key: str = _SUPPORTED_PROJECT
    ) -> dict[str, Any]:
        if project_key != _SUPPORTED_PROJECT:
            raise ForecastConfigEditError(f"unsupported project_key: {project_key!r}")
        normalized = dto.validate_edits(edits)  # raises 400-class on bad input
        edits_root = self._edits_root()  # raises if config-edit root unset / under data root

        grouped, domain_files = self._read_base_snapshot(base_snapshot_id, project_key)

        edit_id = uuid.uuid4().hex[:12]
        created_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005 local stamp
        edit_dir = edits_root / edit_id
        edit_dir.mkdir(parents=True, exist_ok=True)
        base_dir = edit_dir / "base_config"
        edited_dir = edit_dir / "edited_config"

        try:
            dto.emit_base_tree(base_dir, grouped)
            shutil.copytree(base_dir, edited_dir)
            dto.apply_edits(edited_dir, normalized, domain_files)

            snap, parity = self._run_pipeline(edit_dir, edited_dir, edit_id, project_key)
            changed = dto.changed_items(base_dir, edited_dir, normalized, domain_files)
            stored: dict[str, Any] = {
                "edit_id": edit_id,
                "created_stamp": created_stamp,
                "project_key": project_key,
                "base_snapshot_id": base_snapshot_id,
                "status": "succeeded",
                "parity": dto.summarize_parity(parity),
                "snapshot_item_count": int(snap.get("item_count") or 0),
                "snapshot_hashes_by_domain": snap.get("hashes_by_domain") or {},
                "changed_items": changed,
            }
        except ForecastConfigEditError:
            raise
        except Exception as exc:  # noqa: BLE001 — record any pipeline failure as a failed proposal
            stored = {
                "edit_id": edit_id,
                "created_stamp": created_stamp,
                "project_key": project_key,
                "base_snapshot_id": base_snapshot_id,
                "status": "failed",
                "message": f"Config edit proposal did not complete ({type(exc).__name__}).",
            }
        (edit_dir / _EDIT_RECORD).write_text(
            json.dumps(stored, indent=2, sort_keys=True), encoding="utf-8"
        )
        return self._record_to_public(stored)

    def list_edits(self) -> dict[str, Any]:
        records = self._read_all_records(self._edits_root())
        records.sort(key=lambda r: str(r.get("created_stamp") or ""), reverse=True)
        return {
            "surface": _SURFACE + ".edits",
            "edits": [self._record_to_list_item(r) for r in records],
            "guardrails": _guardrails(),
        }

    def read_edit(self, edit_id: str) -> dict[str, Any]:
        rec = self._read_record(self._edits_root(), edit_id)
        if rec is None:
            raise ForecastConfigEditError(f"unknown edit_id: {edit_id!r}")
        return self._record_to_public(rec)

    def read_edit_manifest(self, edit_id: str) -> dict[str, Any]:
        edit_dir = self._edits_root() / edit_id
        manifest_path = edit_dir / "materialized" / "config_snapshot_manifest.json"
        if not manifest_path.exists():
            raise ForecastConfigEditError(f"unknown edit_id: {edit_id!r}")
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = raw.get("files") if isinstance(raw.get("files"), list) else []
        # Rebuild a PATH-FREE manifest: basename + format + row_count + sha256 only.
        safe_files = [
            {
                "name": Path(str(f.get("rel_path") or "")).name,
                "source_format": f.get("source_format"),
                "row_count": int(f.get("row_count") or 0),
                "sha256": f.get("sha256"),
            }
            for f in files
        ]
        return {
            "surface": _SURFACE + ".manifest",
            "edit_id": edit_id,
            "item_count": int(raw.get("item_count") or 0),
            "snapshot_sha256": raw.get("snapshot_sha256"),
            "files": safe_files,
            "guardrails": _guardrails(),
        }

    # -- base snapshot read (live DB, mode=ro) --------------------------------

    def _read_base_snapshot(
        self, base_snapshot_id: str, project_key: str
    ) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], dict[str, str]]:
        conn = self._connect_ro()
        try:
            exists = conn.execute(
                "SELECT 1 FROM forecast_config_snapshots "
                "WHERE config_snapshot_id = ? AND project_key = ?",
                (base_snapshot_id, project_key),
            ).fetchone()
            if exists is None:
                raise ForecastConfigEditError(f"unknown snapshot_id: {base_snapshot_id!r}")
            rows = conn.execute(
                "SELECT s.source_path AS source_path, s.source_format AS source_format, "
                "si.config_domain AS config_domain, si.item_order AS item_order, "
                "si.raw_json AS raw_json "
                "FROM forecast_config_snapshot_items si "
                "JOIN forecast_config_items ci ON ci.config_item_id = si.config_item_id "
                "JOIN forecast_config_sources s ON s.config_source_id = ci.config_source_id "
                "WHERE si.config_snapshot_id = ? "
                "ORDER BY s.source_path, si.item_order",
                (base_snapshot_id,),
            ).fetchall()
        finally:
            conn.close()

        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        domain_files: dict[str, str] = {}
        for r in rows:
            rel, fmt, domain = r["source_path"], r["source_format"], r["config_domain"]
            try:
                obj = json.loads(r["raw_json"])
            except (ValueError, TypeError):
                continue
            if isinstance(obj, dict):
                grouped.setdefault((rel, fmt), []).append(obj)
                # Editable primary file per domain: json for project, jsonl for the others.
                if domain == "project" and fmt == "json":
                    domain_files[domain] = rel
                elif domain != "project" and fmt == "jsonl":
                    domain_files.setdefault(domain, rel)
        if not grouped:
            raise ForecastConfigEditError(f"snapshot has no config items: {base_snapshot_id!r}")
        return grouped, domain_files

    # -- CFR pipeline (isolated DBs only) -------------------------------------

    def _run_pipeline(
        self, edit_dir: Path, edited_dir: Path, edit_id: str, project_key: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if self._cfr_src_override:
            os.environ[ENV_CFR_SRC] = self._cfr_src_override
        _ensure_cfr_importable()  # injects the CFR subrepo src onto sys.path (Phase 3 helper)
        from construction_financial_review.config_registry import (  # noqa: E402
            create_forecast_config_snapshot,
            import_forecast_config_to_db,
            materialize_forecast_config_snapshot,
            run_forecast_config_db_parity,
        )

        edit_db = edit_dir / "edit_db" / "config_registry.sqlite"
        edit_db.parent.mkdir(parents=True, exist_ok=True)
        materialized = edit_dir / "materialized"
        parity_work = edit_dir / "parity_work"

        # import → snapshot → materialize target the ISOLATED edit_db (never the live DB).
        import_forecast_config_to_db(
            config_root=edited_dir,
            db_path=edit_db,
            project_key=project_key,
            import_run_id=f"edit_{edit_id}",
        )
        snap = create_forecast_config_snapshot(
            db_path=edit_db,
            project_key=project_key,
            snapshot_name=f"proposal_{edit_id}",
            snapshot_reason="isolated config-edit proposal",
            created_by=None,  # never personalize the artifact
        )
        materialize_forecast_config_snapshot(
            db_path=edit_db,
            config_snapshot_id=snap["config_snapshot_id"],
            out_root=materialized,
        )
        # parity re-imports edited_config into its OWN temp DB (db_path=None) and refuses the live DB.
        parity = run_forecast_config_db_parity(
            config_root=edited_dir, work_root=parity_work, project_key=project_key
        )
        return snap, parity

    # -- record IO + redacted projection --------------------------------------

    def _record_to_public(self, rec: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {
            "surface": _SURFACE + ".edit",
            "edit_id": rec.get("edit_id"),
            "created_display": friendly_datetime_from_stamp(rec.get("created_stamp")),
            "project_key": rec.get("project_key"),
            "base_snapshot_id": rec.get("base_snapshot_id"),
            "status": rec.get("status"),
            "guardrails": _guardrails(),
        }
        if rec.get("status") == "succeeded":
            out["parity"] = rec.get("parity") or {}
            out["snapshot_item_count"] = int(rec.get("snapshot_item_count") or 0)
            out["snapshot_hashes_by_domain"] = rec.get("snapshot_hashes_by_domain") or {}
            out["changed_items"] = rec.get("changed_items") or []
        else:
            out["message"] = rec.get("message") or "Config edit proposal did not complete."
        return out

    def _record_to_list_item(self, rec: dict[str, Any]) -> dict[str, Any]:
        parity = rec.get("parity") or {}
        return {
            "edit_id": rec.get("edit_id"),
            "created_display": friendly_datetime_from_stamp(rec.get("created_stamp")),
            "status": rec.get("status"),
            "parity_status": parity.get("status"),
            "changed_count": len(rec.get("changed_items") or []),
        }

    def _read_all_records(self, edits_root: Path) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        try:
            children = [p for p in edits_root.iterdir() if p.is_dir()]
        except OSError:
            return out
        for child in children:
            rec = self._read_record(edits_root, child.name)
            if rec is not None:
                out.append(rec)
        return out

    @staticmethod
    def _read_record(edits_root: Path, edit_id: str) -> dict[str, Any] | None:
        path = edits_root / edit_id / _EDIT_RECORD
        if not path.exists():
            return None
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return None
        return obj if isinstance(obj, dict) else None
