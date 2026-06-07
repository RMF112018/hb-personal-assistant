"""Development launcher (HB Assistant Dev).

Launches the current repo checkout against the isolated Dev app-support root using
mock/local data by default (no live Procore/Graph reads). Intended for coding, UI
testing, prompt testing, and local validation.
"""

from __future__ import annotations

from typing import Optional

from hb_assistant.config.models import AppConfig
from hb_assistant.launcher.profiles import resolve_profile
from hb_assistant.launcher.service import LauncherService


def build_dev_service(*, config: Optional[AppConfig] = None) -> LauncherService:
    return LauncherService(resolve_profile("dev", config=config))
