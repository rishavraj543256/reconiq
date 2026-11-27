from datetime import date, timedelta
from decimal import Decimal
from app.reconciliation import Candidate, ReconciliationEngine, Rule


def tx(id, amount, reference, day=0):
    return Candidate(id, Decimal(amount), date(2026, 1, 10) + timedelta(days=day), reference, "Vendor")


def test_exact_matching_is_deterministic_and_prevents_double_matching():
    engine = ReconciliationEngine(); rule = Rule(Decimal("0"), 2, 85, 95)
    results = engine.reconcile([tx("i2", "100", "INV-1"), tx("i1", "100", "INV-1")], [tx("b1", "100", "INV-1")], rule)
    assert len(results) == 1
    assert results[0].left_id == "i1"
    assert results[0].status == "fully_matched"


def test_fuzzy_and_amount_tolerance_matching():
    result = ReconciliationEngine().reconcile([tx("i1", "100.00", "INV-2026-010")], [tx("b1", "102.00", "INV2026010", 2)], Rule(Decimal("3"), 3, 80, 90))[0]
    assert result.confidence >= 90
    assert result.reasoning["amount"]["within_tolerance"] is True


def test_amount_mismatch_is_explained():
    result = ReconciliationEngine().reconcile([tx("i", "100", "INV-9")], [tx("b", "140", "INV-9")], Rule())[0]
    assert result.status == "amount_mismatch"
    assert result.amount_difference == Decimal("40")


def test_one_to_many_uses_decimal_precision():
    result = ReconciliationEngine().reconcile_grouped(tx("i", "0.30", "GROUP"), [tx("a", "0.10", "GROUP"), tx("b", "0.20", "GROUP")], Rule())
    assert result and result.amount_difference == Decimal("0.00")
    assert result.reasoning["component_count"] == 2
