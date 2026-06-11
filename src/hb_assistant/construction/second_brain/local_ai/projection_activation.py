"""Phase 10 — V49 email/calendar projection activation stage.

A thin, raw-free adapter around :mod:`hb_assistant.construction.email_calendar.projection_engine`
so the daily-run pipeline (and operator CLI) can activate the raw -> structured projection as an
explicit stage and surface an honest receipt.

This module adds **no** projection logic of its own. It composes ``projection_engine.reprocess``
(+ ``coverage``) into a single stage receipt carrying counts / statuses / reason codes only:

- ``no_raw_rows`` is reported honestly as a non-failure.
- An unmapped/parity failure for any family degrades/fails the stage WITHOUT a partial projection
  (the engine runs in ``live`` mode, which never raises and never partially projects a degraded
  family — the raw rows remain the system of record).
- If raw rows exist for a family but, after an ``apply``, no structured rows were projected and
  none were skipped as already-higher-quality, the stage is degraded (``zero_structured_after_apply``).

Safety: never makes Graph calls, never performs external writeback, never emits raw values. Apply
mode mutates only the DB on ``db_path`` (idempotent, source-quality-precedence-safe); validation
must pass a ``/tmp`` copy via ``db_path``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from hb_assistant.construction.email_calendar import projection_engine as engine
from hb_assistant.construction.email_calendar import projection_matrix as matrix

STAGE_NAME = "email_calendar_projection"

# Overall stage statuses.
STATUS_OK = "ok"
STATUS_NO_RAW_ROWS = "no_raw_rows"
STATUS_DEGRADED = "degraded"
STATUS_FAILED = "failed"

# Per-family statuses that block (cannot be clean success).
_FAILED_FAMILY_STATUSES = frozenset({matrix.STATUS_FAILED_UNMAPPED, "schema_parity_broken"})


def run_email_calendar_projection_stage(
    *,
    db_path: Optional[str | Path] = None,
    apply: bool = False,
    mode: str = engine.MODE_LIVE,
) -> dict[str, Any]:
    """Activate the V49 email/calendar projection and return a raw-free stage receipt.

    Parameters
    ----------
    db_path:
        Explicit SQLite path. ``None`` uses the default connection. Validation MUST pass a
        ``/tmp`` copy. Apply mode writes structured rows + receipts to this DB only.
    apply:
        ``False`` (default) is a dry run / coverage-only preview (no writes). ``True`` projects
        raw -> structured and records ``email_calendar_projection_runs`` / ``_coverage`` receipts.
    mode:
        Projection enforcement. Defaults to ``live`` so an unmapped family degrades the receipt
        instead of raising (the daily-run stage must fail loud but not crash the pipeline).
    """
    reprocess = engine.reprocess(db_path=db_path, apply=apply, mode=mode, record_receipts=apply)
    cov = engine.coverage(db_path=db_path)

    raw_rows_by_family: dict[str, int] = {}
    structured_rows_by_family: dict[str, int] = {}
    skipped_higher_quality: dict[str, int] = {}
    unmapped_counts: dict[str, int] = {}
    source_quality_distribution: dict[str, dict[str, int]] = {}
    family_statuses: dict[str, str] = {}
    degraded_reason: list[str] = []

    families_out: list[dict[str, Any]] = []
    for fam in reprocess.get("families", []):
        family = str(fam.get("source_family"))
        raw_rows = int(fam.get("raw_parent_rows", 0))
        fam_status = str(fam.get("status", "ok"))
        # apply path exposes projected_parent_rows; dry-run exposes existing-only.
        projected = int(
            fam.get("projected_parent_rows", fam.get("projected_parent_rows_existing", 0))
        )
        skipped = int(fam.get("skipped_higher_quality", 0))
        unmapped = int(fam.get("degraded_unmapped", 0))

        raw_rows_by_family[family] = raw_rows
        structured_rows_by_family[family] = projected
        skipped_higher_quality[family] = skipped
        unmapped_counts[family] = unmapped
        family_statuses[family] = fam_status
        if fam.get("source_quality_distribution"):
            source_quality_distribution[family] = dict(fam["source_quality_distribution"])

        if fam_status in _FAILED_FAMILY_STATUSES:
            degraded_reason.append(f"family_failed:{family}:{fam_status}")
        elif apply and raw_rows > 0 and projected == 0 and skipped == 0:
            degraded_reason.append(f"zero_structured_after_apply:{family}")

        families_out.append(
            {
                "source_family": family,
                "raw_parent_rows": raw_rows,
                "structured_rows": projected,
                "skipped_higher_quality": skipped,
                "unmapped": unmapped,
                "status": fam_status,
                "ok": bool(fam.get("ok", True)),
            }
        )

    any_failed = any(s in _FAILED_FAMILY_STATUSES for s in family_statuses.values())
    all_no_raw = bool(family_statuses) and all(
        s == matrix.STATUS_NO_RAW_ROWS for s in family_statuses.values()
    )

    if any_failed:
        status = STATUS_FAILED
    elif all_no_raw:
        status = STATUS_NO_RAW_ROWS
    elif degraded_reason:
        status = STATUS_DEGRADED
    else:
        status = STATUS_OK

    return {
        "stage": STAGE_NAME,
        "command": "hb-assistant email-calendar raw projection-reprocess",
        "mode": "apply" if apply else "dry_run",
        "status": status,
        "ok": status in (STATUS_OK, STATUS_NO_RAW_ROWS),
        "run_id": reprocess.get("run_id"),
        "raw_rows_by_family": raw_rows_by_family,
        "structured_rows_by_family": structured_rows_by_family,
        "skipped_higher_quality": skipped_higher_quality,
        "unmapped_counts": unmapped_counts,
        "source_quality_distribution": source_quality_distribution,
        "projection_coverage_status": ("complete" if cov.get("ok") else "incomplete"),
        "total_unmapped_business_fields": int(cov.get("total_unmapped_business_fields", 0)),
        "families_with_raw_rows": int(cov.get("families_with_raw_rows", 0)),
        "degraded_reason": degraded_reason,
        "families": families_out,
        "guardrails": {
            "live_graph_calls": int(reprocess.get("live_graph_calls", 0)),
            "external_writeback_performed": int(reprocess.get("external_writeback_performed", 0)),
            "emits_values": False,
        },
    }


__all__ = [
    "STAGE_NAME",
    "STATUS_DEGRADED",
    "STATUS_FAILED",
    "STATUS_NO_RAW_ROWS",
    "STATUS_OK",
    "run_email_calendar_projection_stage",
]
