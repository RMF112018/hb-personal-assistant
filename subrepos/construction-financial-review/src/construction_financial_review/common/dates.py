"""Date normalization + period bucketing for forecast review.

Procore subcontractor pay-app evidence is through May 2026 only; CostEntries may include early June
2026 actuals, which must be bucketed/reported separately.
"""
from __future__ import annotations

from typing import Optional

JUNE_CUTOFF = "2026-06-01"   # < this  -> through_may_2026
JULY_CUTOFF = "2026-07-01"   # >= june, < this -> june_2026_to_date


def normalize_date(value) -> Optional[str]:
    """Return YYYY-MM-DD prefix if parseable-looking, else None."""
    if not value or not isinstance(value, str):
        return None
    ds = value[:10]
    if len(ds) == 10 and ds[4] == "-" and ds[7] == "-":
        return ds
    return None


def period_bucket(date_str, june_cutoff: str = JUNE_CUTOFF, july_cutoff: str = JULY_CUTOFF) -> str:
    """Bucket an accounting date into the forecast-period windows."""
    ds = normalize_date(date_str)
    if ds is None:
        return "undated"
    if ds < june_cutoff:
        return "through_may_2026"
    if ds < july_cutoff:
        return "june_2026_to_date"
    return "after_june_2026"
