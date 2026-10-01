from reconai.split import split_pass
from tests.helpers import row


def test_two_bank_rows_sum_to_one_ledger_row():
    bank = [row("bank_0", "A", 60), row("bank_1", "B", 40)]
    res = split_pass(bank, [row("ledger_0", "X", 100)])
    assert len(res) == 1
    assert res[0]["bank_id"] == "bank_0+bank_1" and res[0]["method"] == "split_payment_rule"


def test_does_not_depend_on_reference_names():
    bank = [row("bank_0", "random1", 30), row("bank_1", "other", 70)]
    assert len(split_pass(bank, [row("ledger_0", "unrelated", 100)])) == 1


def test_ambiguous_split_is_left_for_human_review():
    # 60+40 and 70+30 both explain the ledger amount of 100
    bank = [row("bank_0", "A", 60), row("bank_1", "B", 40),
            row("bank_2", "C", 70), row("bank_3", "D", 30)]
    assert split_pass(bank, [row("ledger_0", "X", 100)]) == []


def test_bank_row_is_not_reused_across_ledger_rows():
    bank = [row("bank_0", "A", 60), row("bank_1", "B", 40)]
    ledger = [row("ledger_0", "X", 100), row("ledger_1", "Y", 100)]
    assert len(split_pass(bank, ledger)) == 1


def test_rejects_when_dates_are_far_apart():
    bank = [row("bank_0", "A", 60, day=1), row("bank_1", "B", 40, day=2)]
    assert split_pass(bank, [row("ledger_0", "X", 100, day=25)]) == []