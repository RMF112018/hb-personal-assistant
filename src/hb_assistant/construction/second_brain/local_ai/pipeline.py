"""Phase 10 — local-agent pipeline orchestration (one repeatable daily run, advisory).

Chains the five proven Phase 10 workflows into a single, stage-bounded, dry-run-default run that
ends in the consumable daily brief:

  follow_up_watch → procore_digest → calendar_prep → daily_brief_synthesis → daily_brief_render

Operator-safety posture:
- **Dry-run by default**; ``--apply`` fail-closed without a per-stage cap.
- **Stage-bounded**: every write stage is capped independently by ``max_persist_per_stage``; an
  optional ``max_total_persist`` global ceiling halts further persistence (remaining stages run
  dry-run) once reached.
- **Fail-loud**: a stage that raises is recorded ``status=failed`` and the run continues so the
  receipt is complete, but the overall ``ok`` is False and ``partial`` is True (the CLI exits
  nonzero unless the operator passes ``--allow-partial``).
- **Stale-brief protection**: ``brief_freshness`` (``fresh`` / ``partial`` / ``preexisting``) plus a
  ``warnings`` list and a banner prepended to the brief markdown make clear when the rendered brief
  does NOT reflect this run (dry-run persists nothing → the brief is pre-existing; a failed
  generation stage → partial).
- **Read-only render / no writeback**: the render stage is read-only; the pipeline never writes a
  file or the Obsidian vault, never persists a run receipt (it is in-memory/structured JSON), and
  never emits raw bodies/URLs/emails/tokens. Candidate persistence flows only through the builders'
  existing guard-clean, capped paths.
"""

from __future__ import annotations

from typing import Any, Optional

from .calendar_prep import build_calendar_prep_candidates
from .daily_brief_render import render_daily_brief
from .daily_brief_synthesis import build_daily_brief_candidates
from .follow_up_watch import run_follow_up_watch_scan
from .procore_digest import build_procore_action_digest

_RENDER_STAGE = "daily_brief_render"
STAGE_ORDER: list[str] = [
    "follow_up_watch",
    "procore_digest",
    "calendar_prep",
    "daily_brief_synthesis",
    _RENDER_STAGE,
]
_GENERATION_STAGES = {"follow_up_watch", "procore_digest", "calendar_prep", "daily_brief_synthesis"}


def _stage_summary_counts(result: Any) -> tuple[int, int]:
    """(would_persist, persisted) from a builder result; 0/0 if absent (e.g. render)."""
    summ = result.get("summary", {}) if isinstance(result, dict) else {}
    return int(summ.get("would_persist", 0) or 0), int(summ.get("persisted", 0) or 0)


def run_local_agent_pipeline(
    *,
    store: Any,
    now_utc: str,
    db_path: Optional[str] = None,
    dry_run: bool = True,
    max_persist_per_stage: Optional[int] = None,
    max_total_persist: Optional[int] = None,
    limit: int = 50,
    lookahead_days: int = 14,
    include_raw: bool = False,
    stages: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Run the Phase 10 local-agent pipeline once (dry-run-first, stage-bounded, fail-loud).

    Apply (``dry_run=False``) requires ``max_persist_per_stage``. Each generation stage is capped
    independently at that value; with ``max_total_persist`` set, stages beyond the global ceiling run
    dry-run. A stage that raises is recorded and the run continues; ``ok`` is False if any stage
    failed. ``brief_freshness`` warns when the rendered brief does not reflect this run.
    """
    if not dry_run and max_persist_per_stage is None:
        raise ValueError("apply requires max_persist_per_stage (per-stage cap on actual persists)")

    brief_date = now_utc[:10]
    selected = [s for s in STAGE_ORDER if (stages is None or s in set(stages))]

    builders: dict[str, tuple[Any, dict[str, Any]]] = {
        "follow_up_watch": (run_follow_up_watch_scan, {}),
        "procore_digest": (build_procore_action_digest, {"db_path": db_path}),
        "calendar_prep": (
            build_calendar_prep_candidates,
            {"db_path": db_path, "lookahead_days": lookahead_days},
        ),
        "daily_brief_synthesis": (build_daily_brief_candidates, {}),
    }

    receipts: list[dict[str, Any]] = []
    total_persisted = 0
    total_would_persist = 0
    total_persist_capped = False
    brief_result: Optional[dict[str, Any]] = None

    for order, name in enumerate(selected, start=1):
        if name == _RENDER_STAGE:
            try:
                brief_result = render_daily_brief(
                    store=store, brief_date=brief_date, limit=limit, include_raw=include_raw
                )
                receipts.append(
                    {
                        "stage": name,
                        "order": order,
                        "status": "ok",
                        "would_persist": 0,
                        "persisted": 0,
                        "detail": brief_result.get("summary", {}),
                    }
                )
            except Exception as e:
                receipts.append(
                    {
                        "stage": name,
                        "order": order,
                        "status": "failed",
                        "would_persist": 0,
                        "persisted": 0,
                        "reason_code": f"stage_error:{type(e).__name__}",
                    }
                )
            continue

        # Effective per-stage cap (honours the optional global ceiling).
        stage_dry_run = dry_run
        eff_cap: Optional[int] = None
        if not dry_run:
            if max_total_persist is not None and total_persisted >= max_total_persist:
                stage_dry_run = True  # global ceiling reached → this write stage runs dry-run
                total_persist_capped = True
            else:
                eff_cap = max_persist_per_stage
                if max_total_persist is not None:
                    eff_cap = min(
                        int(max_persist_per_stage or 0), max_total_persist - total_persisted
                    )

        fn, extra = builders[name]
        kwargs: dict[str, Any] = {
            "store": store,
            "now_utc": now_utc,
            "limit": limit,
            "dry_run": stage_dry_run,
            "max_persist": None if stage_dry_run else eff_cap,
            **extra,
        }
        try:
            result = fn(**kwargs)
            would, persisted = _stage_summary_counts(result)
            receipts.append(
                {
                    "stage": name,
                    "order": order,
                    "status": "ok",
                    "applied": bool(result.get("applied", False)),
                    "would_persist": would,
                    "persisted": persisted,
                    "detail": result.get("summary", {}),
                }
            )
            total_would_persist += would
            total_persisted += persisted
        except Exception as e:
            receipts.append(
                {
                    "stage": name,
                    "order": order,
                    "status": "failed",
                    "would_persist": 0,
                    "persisted": 0,
                    "reason_code": f"stage_error:{type(e).__name__}",
                }
            )

    failed = [r for r in receipts if r["status"] == "failed"]
    ran_generation = [r for r in receipts if r["stage"] in _GENERATION_STAGES]
    failed_generation = [r for r in ran_generation if r["status"] == "failed"]
    ok = not failed
    partial = bool(failed_generation)

    # Freshness: a failed generation stage → partial; no generation ran → preexisting; a dry-run
    # persists nothing so the brief reflects already-persisted candidates → preexisting.
    if not ran_generation:
        brief_freshness = "preexisting"
    elif failed_generation:
        brief_freshness = "partial"
    elif dry_run:
        brief_freshness = "preexisting"
    else:
        brief_freshness = "fresh"

    warnings: list[str] = []
    if brief_freshness == "partial":
        warnings = [f"{r['stage']}:{r.get('reason_code', 'failed')}" for r in failed]
    elif brief_freshness == "preexisting":
        warnings = (
            ["dry_run: brief reflects already-persisted candidates, not this run; apply to refresh"]
            if dry_run and ran_generation
            else ["no_generation_stages_ran: brief reflects already-persisted candidates"]
        )

    brief_view = _brief_view(brief_result, brief_freshness, warnings)

    return {
        "command": "second-brain pipeline run",
        "ok": ok,
        "partial": partial,
        "applied": not dry_run,
        "dry_run": dry_run,
        "now_utc": now_utc,
        "brief_date": brief_date,
        "brief_freshness": brief_freshness,
        "warnings": warnings,
        "stages": receipts,
        "brief": brief_view,
        "summary": {
            "stages_run": len(receipts),
            "stages_ok": len([r for r in receipts if r["status"] == "ok"]),
            "stages_failed": len(failed),
            "total_would_persist": total_would_persist,
            "total_persisted": total_persisted,
            "total_persist_capped": total_persist_capped,
        },
        "guardrails": {
            "dry_run_default": True,
            "apply_requires_per_stage_cap": True,
            "stage_bounded": True,
            "global_cap_enforced": max_total_persist is not None,
            "deterministic_no_clock": True,
            "source_linked": True,
            "no_raw_persistence": True,
            "raw_local_consumption_only": include_raw,
            "no_external_writeback": True,
            "no_vault_write": True,
            "read_only_render": True,
            "advisory_only": True,
        },
    }


def _brief_view(
    brief_result: Optional[dict[str, Any]], freshness: str, warnings: list[str]
) -> dict[str, Any]:
    """Build the brief view, prepending a freshness banner to the markdown when not fresh."""
    if not brief_result:
        return {"summary": {}, "freshness": freshness, "markdown": "", "sections": []}
    markdown = str(brief_result.get("markdown", ""))
    if freshness == "partial":
        banner = "_⚠ Partial brief — one or more generation stages failed; items may be stale or missing._"
        markdown = f"{banner}\n\n{markdown}" if markdown else banner + "\n"
    elif freshness == "preexisting":
        banner = "_ℹ Pre-existing brief — this run persisted nothing; it reflects already-persisted candidates. Apply to refresh._"
        markdown = f"{banner}\n\n{markdown}" if markdown else banner + "\n"
    return {
        "summary": brief_result.get("summary", {}),
        "freshness": freshness,
        "markdown": markdown,
        "sections": brief_result.get("sections", []),
    }
