"""Reconcile missed triggers (dry-run friendly)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReconcileResult:
    missed: int
    replayed: int
    dry_run: bool


def reconcile_missed(*, pending: int, dry_run: bool = True) -> ReconcileResult:
    if dry_run:
        return ReconcileResult(missed=pending, replayed=0, dry_run=True)
    return ReconcileResult(missed=pending, replayed=pending, dry_run=False)
