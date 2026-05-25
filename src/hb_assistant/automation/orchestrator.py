"""MorningRunOrchestrator (Phase 12): bounded production-shaped morning workflow sequencer.

Per D-P12-001:
- Loads config + ledger.
- Applies catch-up (ledger + wake heuristic), weekend gate (manual_only), ledger status.
- Sequences existing stable services (WorkstreamContext, brief, file ingest discover, etc.).
- Isolates stage failures with structured reason (never crashes the run).
- Updates assistant_runs ledger for traceability/catch-up.
- Emits sanitized evidence under PathPolicy evidence dir.
- Dry-run friendly; read-only M365; no full content/tokens in artifacts.

If a capability is unavailable (ImportError or runtime), the stage is skipped with reason.
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hb_assistant.config.loader import load_config
from hb_assistant.config.models import MorningRunConfig
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.links.registry import SourceLinkRegistry
from hb_assistant.store.repositories import Store


class MorningRunOrchestrator:
    """Orchestrates the morning run with gates and existing services."""

    def __init__(self, store: Optional[Store] = None, registry: Optional[SourceLinkRegistry] = None):
        self.store = store or Store()
        self.registry = registry or SourceLinkRegistry(self.store)
        self.pp = PathPolicy()
        self.cfg: MorningRunConfig = load_config().automation.morning_run
        self.evidence_dir = self.pp.get_evidence_dir() / "phase-12-runs"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _record_run(self, run_type: str, dry_run: bool, status: str = "started") -> int:
        return self.registry.record_run(
            run_type=run_type,
            target_date="today",
            trigger="launchd" if not dry_run else "dry-run",
            dry_run=dry_run,
            status=status,
        )

    def _finish_run(self, run_id: int, status: str) -> None:
        self.registry.finish_run(run_id, status=status)

    def _write_evidence(self, payload: Dict[str, Any], suffix: str = "orchestrator") -> Path:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        p = self.evidence_dir / f"morning-{suffix}-{ts}.json"
        # sanitize any accidental full paths/tokens (defense in depth)
        safe = json.dumps(payload, indent=2, default=str)
        for bad in ("token", "access_token", "SECRET", "PRIVATE KEY"):
            safe = safe.replace(bad, "[REDACTED]")
        p.write_text(safe)
        return p

    def _is_weekend(self) -> bool:
        # Simple local weekday; sufficient for MVP (config-driven gate)
        return datetime.now().weekday() >= 5  # Sat=5, Sun=6

    def _last_run_was_before_5am_today(self) -> bool:
        """Heuristic for catch-up: if last morning run started before 05:00 today local, allow catch-up."""
        try:
            summary = self.store.get_summary()
            lr = summary.get("last_run") or {}
            if not lr:
                return True
            started = lr.get("started_at")
            if not started:
                return True
            # naive parse; sufficient
            dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            local_now = datetime.now()
            today_5 = local_now.replace(hour=5, minute=0, second=0, microsecond=0)
            return dt < today_5
        except Exception:
            return True  # fail open for catch-up (ledger is best effort)

    def run(self, dry_run: bool = False) -> Dict[str, Any]:
        """Execute the gated morning workflow. Returns sanitized summary + evidence path."""
        run_id = self._record_run("morning", dry_run=dry_run)

        evidence: Dict[str, Any] = {
            "run_id": run_id,
            "started_at": self._now_iso(),
            "dry_run": dry_run,
            "config": {
                "time": self.cfg.time,
                "weekend_behavior": self.cfg.weekend_behavior,
                "catch_up": self.cfg.catch_up_if_machine_wakes_after,
            },
            "stages": [],
        }

        try:
            # Gate 1: Weekend (20 gate)
            if self._is_weekend() and self.cfg.weekend_behavior == "manual_only":
                evidence["decision"] = "skipped_weekend_manual_only"
                self._finish_run(run_id, "skipped-weekend")
                evidence["evidence_path"] = str(self._write_evidence(evidence))
                return evidence

            # Gate 2: Catch-up (ledger based)
            if self.cfg.catch_up_if_machine_wakes_after and not self._last_run_was_before_5am_today():
                # Recent successful run already happened today before/around 5am; still allow manual kick but note it
                evidence.setdefault("notes", []).append("catch-up not required (recent ledger entry)")

            # Stage execution (use existing services via stable imports; skip on failure)
            stages_order = ["context", "brief_preview", "files_discover"]

            for stage_name in stages_order:
                stage_result: Dict[str, Any] = {"stage": stage_name, "status": "skipped", "reason": None}
                try:
                    if stage_name == "context":
                        from hb_assistant.retrieval import WorkstreamContextBuilder
                        builder = WorkstreamContextBuilder(store=self.store)
                        ctx = builder.build_for_today(limit_per=3)
                        stage_result["status"] = "ok"
                        stage_result["summary"] = {"retrieved": len(ctx.retrieved), "actions": len(ctx.recent_actions)}
                    elif stage_name == "brief_preview":
                        # Use the existing generator (Phase 8); call real method
                        from datetime import date
                        from hb_assistant.obsidian.brief import DailyBriefGenerator
                        gen = DailyBriefGenerator()
                        content, _fm = gen.generate_for_date(date.today())
                        stage_result["status"] = "ok"
                        stage_result["summary"] = {"generated": bool(content), "len": len(content) if content else 0}
                    elif stage_name == "files_discover":
                        from hb_assistant.files import FileIngestionService
                        # DriveItemClient not required for discover stub in dry; service accepts mocks
                        svc = FileIngestionService(drive_client=object())  # type: ignore
                        discovered = svc.discover_and_ingest_pending(limit=3, dry_run=True)
                        stage_result["status"] = "ok"
                        stage_result["summary"] = {"candidates": len(discovered)}
                except Exception as ex:
                    stage_result["status"] = "skipped"
                    stage_result["reason"] = f"{type(ex).__name__}: {str(ex)[:200]}"
                    # continue; isolation per spec

                evidence["stages"].append(stage_result)

            self._finish_run(run_id, "completed-dry-run" if dry_run else "completed")
            evidence["decision"] = "completed"
            evidence["evidence_path"] = str(self._write_evidence(evidence))
            return evidence

        except Exception as top:
            self._finish_run(run_id, "error")
            evidence["decision"] = "error"
            evidence["error"] = str(top)[:300]
            evidence["trace"] = traceback.format_exc()[:2000]
            evidence["evidence_path"] = str(self._write_evidence(evidence))
            return evidence
