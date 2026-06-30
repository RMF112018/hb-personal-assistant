"""Canonical vocabulary for named schedule baseline slots and controls comparison modes."""

from __future__ import annotations

BASELINE_SLOT_KEYS: frozenset[str] = frozenset(
    {
        "current_contract_baseline",
        "previous_progress_update_baseline",
        "secondary_progress_update_baseline",
    }
)

BASELINE_SLOT_LABELS: dict[str, str] = {
    "current_contract_baseline": "Current Contract Baseline",
    "previous_progress_update_baseline": "Previous Progress Update Baseline",
    "secondary_progress_update_baseline": "Secondary Progress Update Baseline",
}

NAMED_COMPARISON_BASIS_VALUES: frozenset[str] = BASELINE_SLOT_KEYS

CONTROLS_COMPARISON_BASIS_VALUES: frozenset[str] = frozenset({"prior_update", *NAMED_COMPARISON_BASIS_VALUES})

CONTROLS_COMPARISON_BASIS_ACCEPTED: frozenset[str] = frozenset(
    {*CONTROLS_COMPARISON_BASIS_VALUES, "baseline"}
)

WORKBENCH_COMPARISON_BASIS_ACCEPTED: frozenset[str] = frozenset(
    {"prior_update", "baseline", *NAMED_COMPARISON_BASIS_VALUES}
)

BASELINE_SLOT_ORDER: tuple[str, ...] = (
    "current_contract_baseline",
    "previous_progress_update_baseline",
    "secondary_progress_update_baseline",
)


def is_named_baseline_basis(comparison_basis: str) -> bool:
    return comparison_basis in NAMED_COMPARISON_BASIS_VALUES


def slot_key_for_basis(comparison_basis: str) -> str | None:
    if comparison_basis in NAMED_COMPARISON_BASIS_VALUES:
        return comparison_basis
    return None


def label_for_slot(slot_key: str) -> str:
    return BASELINE_SLOT_LABELS.get(slot_key, slot_key.replace("_", " ").title())


def normalize_controls_comparison_basis(comparison_basis: str) -> str:
    if comparison_basis in CONTROLS_COMPARISON_BASIS_ACCEPTED:
        return comparison_basis
    return "prior_update"


def comparison_label_for_basis(comparison_basis: str) -> str | None:
    if comparison_basis == "prior_update":
        return "Compared against prior update"
    if comparison_basis == "baseline":
        return "Compared against selected baseline"
    if is_named_baseline_basis(comparison_basis):
        return f"Compared against {label_for_slot(comparison_basis)}"
    return None
