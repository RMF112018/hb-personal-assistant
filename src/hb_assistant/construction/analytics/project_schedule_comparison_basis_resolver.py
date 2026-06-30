"""Resolve schedule comparison_basis values with explicit source-model boundaries."""

from __future__ import annotations

from dataclasses import dataclass

from .project_schedule_baseline_vocabulary import (
    WORKBENCH_COMPARISON_BASIS_ACCEPTED,
    is_named_baseline_basis,
)


@dataclass(frozen=True)
class ResolvedComparisonBasis:
    comparison_basis: str
    source_model: str
    preview_basis: str
    slot_key: str | None = None


def resolve_workbench_comparison_basis(comparison_basis: str) -> ResolvedComparisonBasis:
    if comparison_basis not in WORKBENCH_COMPARISON_BASIS_ACCEPTED:
        raise ValueError("invalid_comparison_basis")
    if comparison_basis == "prior_update":
        return ResolvedComparisonBasis(
            comparison_basis="prior_update",
            source_model="prior_update",
            preview_basis="prior_update",
        )
    if comparison_basis == "baseline":
        return ResolvedComparisonBasis(
            comparison_basis="baseline",
            source_model="legacy_v90",
            preview_basis="baseline",
        )
    if is_named_baseline_basis(comparison_basis):
        return ResolvedComparisonBasis(
            comparison_basis=comparison_basis,
            source_model="named_slot",
            preview_basis="baseline",
            slot_key=comparison_basis,
        )
    raise ValueError("invalid_comparison_basis")


def reconcile_driver_detail_comparison_params(
    *,
    comparison_basis: str | None,
    basis: str | None,
) -> str:
    if comparison_basis is not None and basis is not None and comparison_basis != basis:
        raise ValueError("conflicting_comparison_params")
    raw = comparison_basis or basis or "prior_update"
    return resolve_workbench_comparison_basis(raw).comparison_basis
