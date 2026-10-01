import csv
import json

from reconai.engine import reconcile, run
from tests.helpers import row


def test_each_pass_sees_only_unmatched_rows():
    bank = [row("bank_0", "INV-1", 100), row("bank_1", "INV-2O", 200, day=11),
            row("bank_2", "S-A", 60), row("bank_3", "S-B", 40)]
    ledger = [row("ledger_0", "INV-1", 100), row("ledger_1", "INV-20", 200),
              row("ledger_2", "S", 100)]
    report, queue = reconcile(bank, ledger)
    methods = sorted(m["method"] for m in report["matches"])
    assert methods == ["exact", "fuzzy", "split_payment_rule"]
    assert report["match_rate_pct"] == 100.0
    assert report["exceptions"] == [] and queue == []


def test_unresolvable_rows_become_exceptions_not_forced_matches():
    report, queue = reconcile([row("bank_0", "AAA", 100)], [row("ledger_0", "ZZZ", 9000)])
    assert report["matches"] == []
    assert {e["side"] for e in report["exceptions"]} == {"bank", "ledger"}
    assert queue == []


def test_ambiguous_rows_go_to_review_queue_with_zero_confidence_without_api_key():
    report, queue = reconcile([row("bank_0", "AAA", 1000)], [row("ledger_0", "ZZZ", 1200)])
    assert report["matches"] == []
    assert len(queue) == 1 and queue[0]["llm_verdict"]["confidence"] == 0
    assert "needs_llm_review" in report["exceptions"][0]["reason"]


def test_empty_input_does_not_divide_by_zero():
    report, _ = reconcile([], [])
    assert report["match_rate_pct"] == 0.0


def test_run_reads_csvs_and_writes_outputs(tmp_path):
    data, out = tmp_path / "data", tmp_path / "out"
    data.mkdir()
    with open(data / "bank_statement.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "description", "amount", "reference_no"])
        w.writerow(["2026-08-10", "ACME LTD", "100.00", "INV-1"])
    with open(data / "internal_ledger.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["txn_date", "narration", "amount", "ref_id"])
        w.writerow(["2026-08-10", "ACME LTD", "100.00", "INV-1"])
    report, _ = run(str(data), str(out))
    assert report["match_rate_pct"] == 100.0
    saved = json.loads((out / "reconciliation_report.json").read_text())
    assert saved["matches"][0]["bank_id"] == "bank_0"
    assert (out / "review_queue.json").exists()