"""Map final-value controls to canonical BudgetDetails budget_code_keys.

The mapping rules are identical to the timing-control layer (explicit ``budget_code_key`` must be
canonical; a ``cost_code``-only control resolves only when exactly one canonical key carries that cost
code, else it is ambiguous and fails closed), so we reuse the proven ``forecast_controls.mapping``
implementation verbatim rather than duplicate it.
"""
from __future__ import annotations

from ..forecast_controls.mapping import (  # noqa: F401 - re-exported for this contract
    M_AMBIGUOUS,
    M_EXPLICIT,
    M_INVENTED,
    M_MISSING,
    M_RESOLVED,
    M_UNMAPPED,
    MAPPED_STATUSES,
    cost_code_to_keys,
    map_control,
)
