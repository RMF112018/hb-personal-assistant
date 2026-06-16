"""Decimal money helpers. NEVER use float for financial math — always Decimal(str(value))."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, getcontext
from typing import Iterable, Optional

getcontext().prec = 50

CENTS = Decimal("0.01")
MATERIALITY_ABSOLUTE = Decimal("25000")
MATERIALITY_PERCENT = Decimal("0.10")


def dec(v) -> Optional[Decimal]:
    """Decimal(str(v)) or None for null/blank/non-numeric. No float arithmetic."""
    if v is None:
        return None
    if isinstance(v, str) and v.strip() == "":
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def D(v) -> Decimal:
    """Decimal or zero."""
    d = dec(v)
    return d if d is not None else Decimal("0")


def money_str(v) -> Optional[str]:
    """Canonical 2-decimal money string, or None."""
    d = dec(v)
    return None if d is None else str(d.quantize(CENTS))


def dsum(values: Iterable) -> Decimal:
    """Decimal sum over raw values; non-numeric ignored."""
    total = Decimal("0")
    for v in values:
        d = dec(v)
        if d is not None:
            total += d
    return total


def materiality(a, b, abs_threshold: Decimal = MATERIALITY_ABSOLUTE,
                pct_threshold: Decimal = MATERIALITY_PERCENT):
    """Return (gap, pct, is_material) for |a-b|. Material iff gap>=abs AND pct>=pct_threshold."""
    da = D(a)
    db = D(b)
    gap = abs(da - db)
    basis = max(abs(da), abs(db))
    pct = (gap / basis) if basis > 0 else None
    is_material = gap >= abs_threshold and pct is not None and pct >= pct_threshold
    return gap, pct, is_material
