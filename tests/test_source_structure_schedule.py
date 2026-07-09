"""PREVIEW-ONLY launchd builder for the scheduled source-structure refresh.

Proves the builder produces a valid job definition WITHOUT loading it: no plist is written and
launchctl is never invoked (install stays a separate future operator command).
"""

from __future__ import annotations

import plistlib
import subprocess

from hb_assistant.automation.source_structure_launchd import build_refresh_job
from hb_assistant.config.models import SourceStructureScheduleConfig


def test_build_refresh_job_is_valid_and_default_off():
    job = build_refresh_job(SourceStructureScheduleConfig(), output_root="/tmp/ev")
    assert job["action"] == "preview_only"
    assert job["enabled"] is False  # schedule is opt-in
    args = job["program_arguments"]
    assert args[1:3] == ["source-structure", "refresh"]
    assert "--apply" in args
    # Renders a parseable plist without loading it.
    parsed = plistlib.loads(job["plist_xml"].encode("utf-8"))
    assert parsed["Label"] == SourceStructureScheduleConfig().label
    assert parsed["StartCalendarInterval"] == {"Hour": 3, "Minute": 0}


def test_build_refresh_job_honors_schedule_time():
    job = build_refresh_job(
        SourceStructureScheduleConfig(schedule_time="22:45"), output_root="/tmp/ev")
    assert job["plist"]["StartCalendarInterval"] == {"Hour": 22, "Minute": 45}
    assert job["schedule_time"] == "22:45"


def test_builder_never_invokes_launchctl(monkeypatch):
    """The builder must not load/bootstrap anything — subprocess is never called."""
    calls: list[tuple] = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: calls.append(a))
    job = build_refresh_job(SourceStructureScheduleConfig(enabled=True), output_root="/tmp/ev")
    assert calls == []
    # Commands are informational strings only — present but never executed.
    assert all(isinstance(c, str) for c in job["install_commands"])
    assert "PREVIEW ONLY" in job["note"]
