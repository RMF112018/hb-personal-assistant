"""Production launcher (HB Assistant).

Launches the current installed/packaged build against the production app-support DB
and configuration, and runs the scheduled source-refresh per production policy
(live external reads are config-gated and OFF by default). Intended for daily
operator use.
"""

from __future__ import annotations

from typing import Optional

from hb_assistant.config.models import AppConfig
from hb_assistant.launcher.profiles import resolve_profile
from hb_assistant.launcher.service import LauncherService


def build_production_service(*, config: Optional[AppConfig] = None) -> LauncherService:
    return LauncherService(resolve_profile("production", config=config))
