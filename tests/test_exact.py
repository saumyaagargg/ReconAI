from reconai.exact import exact_pass
from tests.helpers import row


def test_matches_same_ref_amount_date():
    res = exact_pass([row("bank_0", "INV-1", 100)], [row("ledger_0", "INV-1", 100)])
    assert [(r["bank_id"], r["ledger_id"], r["method"]) for r in res] == [("bank_0", "ledger_0", "exact")]
    assert res[0]["confidence"] == 1.0


def test_different_date_is_not_exact():
    assert exact_pass([row("bank_0", "INV-1", 100, day=10)],
                      [row("ledger_0", "INV-1", 100, day=11)]) == []


def test_ledger_row_used_only_once():
    bank = [row("bank_0", "INV-1", 100), row("bank_1", "INV-1", 100)]
    res = exact_pass(bank, [row("ledger_0", "INV-1", 100)])
    assert len(res) == 1