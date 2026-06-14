from decimal import Decimal

from construction_financial_review.common.money import dec, D, money_str, dsum, materiality


def test_dec_and_none():
    assert dec("1032.4") == Decimal("1032.4")
    assert dec(None) is None
    assert dec("") is None
    assert dec("not-a-number") is None
    assert D(None) == Decimal("0")


def test_money_str_two_decimals():
    assert money_str("1032.4") == "1032.40"
    assert money_str(6700) == "6700.00"
    assert money_str("-3791.66") == "-3791.66"
    assert money_str(None) is None


def test_dsum_decimal_no_float():
    total = dsum(["172.02", "1.1", None, "", "x", 2])
    assert total == Decimal("175.12")
    assert isinstance(total, Decimal)


def test_materiality_gate_25k_10pct():
    # basis = max(|a|,|b|) = 300000; gap 30000 -> exactly 10% and >=25k -> material
    gap, pct, mat = materiality(Decimal("300000"), Decimal("270000"))
    assert gap == Decimal("30000") and pct == Decimal("0.1") and mat is True
    # gap 9.09% (< 10%) even though >=25k -> NOT material (basis is the larger value)
    _, _, mat_pct = materiality(Decimal("330000"), Decimal("300000"))
    assert mat_pct is False
    # gap 20000 -> below absolute threshold -> not material
    _, _, mat2 = materiality(Decimal("120000"), Decimal("100000"))
    assert mat2 is False
    # large dollar but tiny pct -> not material
    _, _, mat3 = materiality(Decimal("10026000"), Decimal("10000000"))
    assert mat3 is False
