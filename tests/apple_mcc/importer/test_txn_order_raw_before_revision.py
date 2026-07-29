"""Documented order: snapshot then revision then observation."""

ORDER = ("snapshot", "revision", "observation", "selection")

def test_order():
    assert ORDER[0] == "snapshot"
