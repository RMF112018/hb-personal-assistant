"""Launchd automation and MorningRunOrchestrator (Phase 12).

LaunchdManager: renders and manages user LaunchAgent for scheduled morning runs.
MorningRunOrchestrator: bounded production-shaped sequencer for the morning workflow
  (applies catch-up/weekend/ledger gates per config, sequences existing services,
   isolates failures with reasons, writes sanitized evidence).

All paths config-driven via PathPolicy + load_config().automation.morning_run.
Dry-run friendly, read-only M365, no full secrets in artifacts.
"""

from .launchd_manager import LaunchdManager
from .orchestrator import MorningRunOrchestrator

__all__ = ["LaunchdManager", "MorningRunOrchestrator"]
