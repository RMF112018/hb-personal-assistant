"""Per-code historical-forecast signal: remaining-forecast series, scores, pattern + curve shape.

Deterministic. For each forecast snapshot (workbook tab) the REMAINING forecast is the sum of
forecast-classified amounts for periods after the snapshot month. The series across snapshots yields
movement (slope), persistence, stability/volatility, and a pattern class; the latest snapshot's monthly
amounts yield a curve-shape classification. All money is Decimal; nothing here is treated as actual cost.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from decimal import Decimal

from ..common.money import D, dsum, money_str

ZERO = Decimal("0")
ZERO_EPS = Decimal("1")          # remaining forecast <= $1 treated as zero-remaining
FLAT_REL = Decimal("0.05")       # |relative slope| below this is "flat"
VOLATILE_COV = Decimal("0.75")
SPIKE_SHARE = Decimal("0.55")    # one month holding >55% of the curve is a spike

# historical_pattern_class
P_INACTIVE = "inactive"
P_STABLE_ZERO = "stable_zero"
P_STABLE_NONZERO = "stable_nonzero"
P_INCREASING = "increasing_exposure"
P_DECREASING = "decreasing_tapering_exposure"
P_VOLATILE = "volatile_review"
P_SPARSE = "sparse_insufficient_history"

# curve_shape_class
C_INACTIVE = "inactive"
C_STABLE_ZERO = "stable_zero"
C_FLAT = "flat"
C_LINEAR = "linear"
C_FRONT = "front_loaded"
C_BACK = "back_loaded"
C_SCURVE = "s_curve"
C_TAPER = "tapering_closeout"
C_SPIKE = "spike"
C_VOLATILE = "volatile_review"


def _q4(x: Decimal) -> str:
    return str(Decimal(x).quantize(Decimal("0.0001")))


def _mean(vals):
    return (sum(vals, ZERO) / Decimal(len(vals))) if vals else ZERO


def _std(vals):
    if len(vals) < 2:
        return ZERO
    m = _mean(vals)
    var = sum(((v - m) ** 2 for v in vals), ZERO) / Decimal(len(vals))
    return var.sqrt()


def _cov(vals):
    m = _mean(vals)
    if m == 0:
        return ZERO
    return (_std(vals) / m).copy_abs()


def _slope(vals):
    """Least-squares slope of vals over ordinal index 0..n-1 (Decimal, deterministic)."""
    n = len(vals)
    if n < 2:
        return ZERO
    xs = [Decimal(i) for i in range(n)]
    mx, my = _mean(xs), _mean(vals)
    num = sum(((xs[i] - mx) * (vals[i] - my) for i in range(n)), ZERO)
    den = sum(((x - mx) ** 2 for x in xs), ZERO)
    return (num / den) if den != 0 else ZERO


def snapshot_remaining_series(rows: list) -> "OrderedDict[str, Decimal]":
    """{snapshot_month: remaining forecast} = sum of forecast-classified future amounts per snapshot."""
    by_snap: dict = defaultdict(list)
    for r in rows:
        if r.get("classification") != "forecast":
            continue
        amt = r.get("amount")
        if amt is None:
            continue
        snap, pm = r.get("snapshot_month"), r.get("period_month")
        if snap and pm and pm > snap:
            by_snap[snap].append(D(amt))
    return OrderedDict((s, dsum(by_snap[s])) for s in sorted(by_snap))


def latest_monthly_curve(rows: list) -> list:
    """[(period_month, amount)] for the latest snapshot's future forecast periods, ascending."""
    snaps = sorted({r.get("snapshot_month") for r in rows if r.get("snapshot_month")})
    if not snaps:
        return []
    latest = snaps[-1]
    by_month: dict = defaultdict(list)
    for r in rows:
        if r.get("snapshot_month") != latest or r.get("classification") != "forecast":
            continue
        amt, pm = r.get("amount"), r.get("period_month")
        if amt is not None and pm and pm > latest:
            by_month[pm].append(D(amt))
    return [(m, dsum(by_month[m])) for m in sorted(by_month)]


def classify_curve_shape(curve: list) -> str:
    """Classify the monthly forecast curve shape deterministically."""
    vals = [v for _, v in curve]
    if not vals:
        return C_INACTIVE
    total = sum(vals, ZERO)
    if total <= ZERO_EPS:
        return C_STABLE_ZERO
    n = len(vals)
    if n == 1:
        return C_SPIKE if vals[0] > 0 else C_STABLE_ZERO
    peak = max(vals)
    if peak / total >= SPIKE_SHARE and n >= 3:
        return C_SPIKE
    cov = _cov(vals)
    half = n // 2
    first_half = sum(vals[:half], ZERO)
    second_half = sum(vals[n - half:], ZERO)
    # tapering: trends to (near) zero at the tail
    if vals[-1] <= ZERO_EPS < vals[0] and second_half < first_half:
        return C_TAPER
    if cov <= Decimal("0.15"):
        return C_FLAT
    # monotonic trends are directional, not volatile — check before the volatility test
    is_increasing = all(vals[i] <= vals[i + 1] for i in range(n - 1)) and vals[-1] > vals[0]
    is_decreasing = all(vals[i] >= vals[i + 1] for i in range(n - 1)) and vals[0] > vals[-1]
    if is_increasing:
        return C_BACK
    if is_decreasing:
        return C_FRONT
    # s-curve: middle months heavier than the ends
    mid = sum(vals[1:n - 1], ZERO)
    if n >= 5 and vals[0] < peak and vals[-1] < peak and mid >= first_half and mid >= second_half:
        return C_SCURVE
    if cov >= VOLATILE_COV:
        return C_VOLATILE
    if second_half > first_half:
        return C_BACK
    if first_half > second_half:
        return C_FRONT
    return C_LINEAR


def _zero_persistence(series_vals) -> tuple:
    """(fraction zero, trailing consecutive zero count)."""
    if not series_vals:
        return ZERO, 0
    zero_flags = [v <= ZERO_EPS for v in series_vals]
    frac = Decimal(sum(1 for z in zero_flags if z)) / Decimal(len(zero_flags))
    trailing = 0
    for z in reversed(zero_flags):
        if z:
            trailing += 1
        else:
            break
    return frac, trailing


def pattern_class(series, cov, slope, rel_slope) -> str:
    vals = list(series.values())
    if len(vals) < 2:
        return P_SPARSE
    if all(v <= ZERO_EPS for v in vals):
        return P_INACTIVE
    frac_zero, trailing_zero = _zero_persistence(vals)
    if trailing_zero >= 2 and vals[-1] <= ZERO_EPS:
        return P_STABLE_ZERO
    if cov >= VOLATILE_COV:
        return P_VOLATILE
    if rel_slope >= FLAT_REL:
        return P_INCREASING
    if rel_slope <= -FLAT_REL:
        return P_DECREASING
    return P_STABLE_NONZERO


def build_signal(cost_code: str, rows: list, mapping: dict, project_key: str) -> OrderedDict:
    series = snapshot_remaining_series(rows)
    vals = list(series.values())
    mean = _mean(vals)
    std = _std(vals)
    cov = _cov(vals)
    slope = _slope(vals)
    rel_slope = (slope / mean) if mean > 0 else ZERO
    frac_zero, trailing_zero = _zero_persistence(vals)
    pclass = pattern_class(series, cov, slope, rel_slope)
    curve = latest_monthly_curve(rows)
    cshape = classify_curve_shape(curve)
    stability = max(ZERO, Decimal("1") - min(Decimal("1"), cov))
    volatility = min(Decimal("1"), cov)
    # signal strength: snapshot density (capped at 6) blended with nonzero presence
    density = min(Decimal("1"), Decimal(len(vals)) / Decimal("6"))
    nonzero_share = Decimal("1") - frac_zero
    signal_strength = (density * Decimal("0.6") + nonzero_share * Decimal("0.4"))
    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", mapping.get("budget_code_key")),
        ("mapping_status", mapping.get("mapping_status")),
        ("mapping_method", mapping.get("mapping_method")),
        ("mapping_confidence", _q4(Decimal(str(mapping.get("mapping_confidence", 0))))),
        ("cost_code", cost_code),
        ("category", _category(mapping)),
        ("budget_code_description", _desc(rows)),
        ("historical_source_package", "+".join(mapping.get("source_packages") or [])),
        ("historical_source_workbooks", sorted({r.get("source_workbook") for r in rows if r.get("source_workbook")})),
        ("source_row_count", mapping.get("source_row_count")),
        ("forecast_snapshot_count", len(vals)),
        ("forecast_months_observed", list(series.keys())),
        ("latest_historical_forecast_month", list(series.keys())[-1] if series else None),
        ("historical_remaining_forecast_latest", money_str(vals[-1]) if vals else None),
        ("historical_remaining_forecast_min", money_str(min(vals)) if vals else None),
        ("historical_remaining_forecast_max", money_str(max(vals)) if vals else None),
        ("historical_remaining_forecast_mean", money_str(mean) if vals else None),
        ("historical_remaining_forecast_stddev", money_str(std) if vals else None),
        ("historical_forecast_slope", money_str(slope) if vals else None),
        ("historical_forecast_relative_slope", _q4(rel_slope)),
        ("historical_pattern_class", pclass),
        ("latest_curve_shape_class", cshape),
        ("zero_remaining_persistence_score", _q4(frac_zero)),
        ("trailing_zero_snapshot_count", trailing_zero),
        ("forecast_stability_score", _q4(stability)),
        ("forecast_volatility_score", _q4(volatility)),
        ("historical_signal_strength", _q4(signal_strength)),
        ("duplicate_cost_code_warning", mapping.get("duplicate_cost_code_warning")),
        ("description_sensitive_review", mapping.get("description_sensitive_review")),
        ("requires_human_acceptance", True),
    ])


def build_curve_rows(cost_code: str, rows: list, mapping: dict, project_key: str) -> list:
    """Latest-snapshot monthly curve rows (one per future forecast month)."""
    snaps = sorted({r.get("snapshot_month") for r in rows if r.get("snapshot_month")})
    if not snaps:
        return []
    latest = snaps[-1]
    curve = latest_monthly_curve(rows)
    cshape = classify_curve_shape(curve)
    total = sum((v for _, v in curve), ZERO)
    out = []
    for pm, amt in curve:
        weight = (amt / total) if total > 0 else ZERO
        src_rows = sorted({r.get("source_row") for r in rows
                           if r.get("snapshot_month") == latest and r.get("period_month") == pm
                           and r.get("source_row") is not None})
        out.append(OrderedDict([
            ("project_key", project_key),
            ("budget_code_key", mapping.get("budget_code_key")),
            ("cost_code", cost_code),
            ("forecast_snapshot_month", latest),
            ("period_month", pm),
            ("period_classification", "forecast"),
            ("historical_forecast_amount", money_str(amt)),
            ("curve_weight", _q4(weight)),
            ("curve_shape_class", cshape),
            ("source_package", "+".join(mapping.get("source_packages") or [])),
            ("source_rows", src_rows),
            ("mapping_confidence", _q4(Decimal(str(mapping.get("mapping_confidence", 0))))),
            ("requires_human_acceptance", True),
        ]))
    return out


def _category(mapping):
    key = mapping.get("budget_code_key")
    if key:
        parts = key.split(".")
        if len(parts) == 3:
            return parts[2]
    return None


def _desc(rows):
    for r in rows:
        if r.get("description"):
            return r["description"]
    return None
