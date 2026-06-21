"""Forecast config promotion (Implementation Phase E2) — the first analytics live-DB write.

Takes an APPROVED Phase E proposal (status ``succeeded`` + parity ``pass``) and certify-promotes it
into the LIVE v60 config-registry DB as a new snapshot, by orchestrating the CFR gated-write workflow
``run_live_db_config_registry_promotion`` (backup → single txn → certification). It is gated three ways:
an explicit default-OFF opt-in (``HB_FORECAST_PROMOTION_ENABLED``), an explicit per-request ``confirm``,
and the proposal must already be parity-passed. It records a redacted audit block on the proposal.

The returned payload is redaction-safe (sha + counts + decision + booleans; every path/stamp from the
workflow report is stripped — only a friendly display of the stamp crosses the boundary).
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from hb_assistant.construction.analytics.forecast_config_edit_service import (
    resolve_config_edit_root,
)
from hb_assistant.construction.analytics.forecast_dto import friendly_datetime_from_stamp
from hb_assistant.construction.analytics.forecast_run_service import (
    ENV_CFR_SRC,
    _ensure_cfr_importable,
)

_SURFACE = "analytics.forecast_config_promotion"
_EDITS_DIRNAME = "edits"
_EDIT_RECORD = "edit_record.json"
_DECISION_CERTIFIED = "live_db_config_registry_certified"


class ForecastConfigPromotionError(RuntimeError):
    """Raised when a promotion is refused. The message is a path-free reason code."""


def _guardrails() -> dict[str, Any]:
    return {
        "writes_live_config_db": True,
        "backup_created": True,
        "additive_snapshot_only": True,
        "lineage_only_not_generation": True,
        "no_live_data_root_write": True,
        "no_llm": True,
        "local_first": True,
    }


class ForecastConfigPromotionService:
    """Promotes a parity-passed config-edit proposal into the live config DB (gated + backed up)."""

    def __init__(
        self,
        config_edit_root: str | None = None,
        db_path: str | None = None,
        cfr_src: str | None = None,
        promotion_enabled: bool = False,
    ) -> None:
        self._config_edit_root_override = config_edit_root
        self._db_path_override = db_path
        self._cfr_src_override = cfr_src
        self._promotion_enabled = bool(promotion_enabled)

    def _edits_root(self) -> Path:
        return resolve_config_edit_root(self._config_edit_root_override) / _EDITS_DIRNAME

    def promote_config_edit(self, edit_id: str, confirm: bool = False) -> dict[str, Any]:
        if not self._promotion_enabled:
            raise ForecastConfigPromotionError("promotion disabled")
        if confirm is not True:
            raise ForecastConfigPromotionError("not confirmed")

        edits_root = self._edits_root()  # raises if the config-edit root is unset / under data root
        edit_dir = edits_root / edit_id
        record_path = edit_dir / _EDIT_RECORD
        if not record_path.exists():
            raise ForecastConfigPromotionError(f"unknown edit_id: {edit_id!r}")
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise ForecastConfigPromotionError(f"unknown edit_id: {edit_id!r}") from exc
        if not isinstance(record, dict) or record.get("status") != "succeeded":
            raise ForecastConfigPromotionError("proposal not eligible: not a succeeded proposal")
        if (record.get("parity") or {}).get("status") != "pass":
            raise ForecastConfigPromotionError("proposal not eligible: parity did not pass")

        edited_config = edit_dir / "edited_config"
        if not edited_config.is_dir():
            raise ForecastConfigPromotionError("proposal not eligible: edited config is unavailable")

        project_key = record.get("project_key") or "tropical"
        expected_item_count = record.get("snapshot_item_count")
        expected_hashes = record.get("snapshot_hashes_by_domain") or {}
        context_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005 local stamp
        work_root = edits_root.parent / "promotions" / edit_id / context_stamp

        if self._cfr_src_override:
            os.environ[ENV_CFR_SRC] = self._cfr_src_override
        _ensure_cfr_importable()
        from construction_financial_review.workflows.live_db_config_registry_promotion import (
            LiveDbConfigRegistryPromotionError,
            run_live_db_config_registry_promotion,
        )

        try:
            report = run_live_db_config_registry_promotion(
                edited_config_root=edited_config,
                work_root=work_root,
                context_stamp=context_stamp,
                live_db_path=Path(self._db_path_override) if self._db_path_override else None,
                project_key=project_key,
                allow_live_db_write=True,
                snapshot_name=f"promotion_{edit_id}",
                snapshot_reason="certified live promotion of approved config-edit proposal",
                expected_item_count=expected_item_count,
                expected_hashes_by_domain=expected_hashes,
            )
        except LiveDbConfigRegistryPromotionError as exc:
            raise ForecastConfigPromotionError(f"promotion failed: {type(exc).__name__}") from exc

        certified = report.get("decision") == _DECISION_CERTIFIED
        cert_block = report.get("promotion_certification") or {}
        # Record a redacted promotion block on the proposal (safe fields only; no paths).
        record["promotion"] = {
            "context_stamp": context_stamp,
            "promoted_snapshot_id": report.get("promoted_snapshot_id"),
            "item_count": int(report.get("item_count") or 0),
            "decision": report.get("decision"),
            "status": "promoted" if certified else "not_ready",
            "backup_created": bool(report.get("backup")),
        }
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")

        return {
            "surface": _SURFACE + ".promote",
            "edit_id": edit_id,
            "status": "promoted" if certified else "not_ready",
            "promoted_snapshot_id": report.get("promoted_snapshot_id"),
            "item_count": int(report.get("item_count") or 0),
            "certification": {
                "decision": cert_block.get("decision"),
                "non_tropical_preserved": bool(cert_block.get("pre_existing_snapshots_preserved")),
            },
            "backup_created": bool(report.get("backup")),
            "created_display": friendly_datetime_from_stamp(context_stamp),
            "guardrails": _guardrails(),
        }
