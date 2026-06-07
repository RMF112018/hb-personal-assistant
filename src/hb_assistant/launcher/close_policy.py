"""Window/session close policy: Quit vs Run-in-Background.

Quit terminates every managed process and writes a clean shutdown receipt.
Run-in-Background terminates only the UI/foreground surfaces, keeps the
``keep_in_background`` services (MCP, scheduler) alive, and marks the session
background-active so it can be inspected and stopped later.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hb_assistant.launcher.models import CloseAction
from hb_assistant.launcher.process_manager import ProcessManager
from hb_assistant.launcher.profiles import Profile
from hb_assistant.source_refresh.orchestrator import _safe_git_sha


class ClosePolicy:
    def __init__(self, profile: Profile, manager: ProcessManager) -> None:
        self.profile = profile
        self.manager = manager

    def apply(self, action: CloseAction) -> dict[str, Any]:
        state = self.manager.load_session()
        terminated: list[str] = []
        kept: list[str] = []

        for rec in state.processes:
            if action == "background" and rec.keep_in_background:
                if self.manager.is_alive(rec.pid):
                    kept.append(rec.name)
                continue
            status = self.manager.terminate(rec)
            rec.status = status
            terminated.append(rec.name)

        scheduler_active = False
        if action == "background":
            state.processes = [r for r in state.processes if r.keep_in_background]
            state.background_active = True
            scheduler_active = self.profile.scheduler_enabled and any(
                r.name == "scheduler" for r in state.processes
            )
        else:  # quit
            state.processes = []
            state.background_active = False

        receipt = self._receipt(action, terminated, kept, scheduler_active)
        state.last_shutdown_receipt = receipt["receipt_path"]
        self.manager.save_session(state)
        return receipt

    def _receipt(
        self, action: CloseAction, terminated: list[str], kept: list[str], scheduler_active: bool
    ) -> dict[str, Any]:
        ts = datetime.now(timezone.utc).isoformat()
        receipt: dict[str, Any] = {
            "command": "launcher close",
            "generated_utc": ts,
            "repo_sha": _safe_git_sha(),
            "environment": self.profile.environment,
            "action": action,
            "terminated": terminated,
            "kept_alive": kept,
            "background_active": action == "background",
            "scheduler_active": scheduler_active,
            "metadata_only": True,
            "status": "ok",
        }
        out_dir = self.profile.evidence_path / "launcher"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"close-{action}-{self.profile.environment}.json"
        import json

        path.write_text(json.dumps(receipt, indent=2, sort_keys=True))
        receipt["receipt_path"] = str(path)
        return receipt
