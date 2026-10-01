from reconai.fuzzy import fuzzy_pass
from tests.helpers import row


def test_matches_typo_in_ref_with_small_amount_and_date_gap():
    res = fuzzy_pass([row("bank_0", "INV-1001", 100, day=10)],
                     [row("ledger_0", "INV-1O01", 101.5, day=11)])
    assert len(res) == 1 and res[0]["method"] == "fuzzy"
    assert 0.75 <= res[0]["confidence"] < 1.0


def test_rejects_amount_outside_tolerance():
    assert fuzzy_pass([row("bank_0", "INV-1001", 100)],
                      [row("ledger_0", "INV-1001", 110)]) == []


def test_rejects_date_outside_window():
    assert fuzzy_pass([row("bank_0", "INV-1001", 100, day=10)],
                      [row("ledger_0", "INV-1001", 100, day=20)]) == []


def test_rejects_dissimilar_reference():
    assert fuzzy_pass([row("bank_0", "INV-1001", 100)],
                      [row("ledger_0", "ZZZZZZZZ", 100)]) == []


def test_picks_best_scoring_candidate():
    res = fuzzy_pass([row("bank_0", "INV-1001", 100)],
                     [row("ledger_0", "INV-1099", 100), row("ledger_1", "INV-1001X", 100)])
    assert res[0]["ledger_id"] == "ledger_1"